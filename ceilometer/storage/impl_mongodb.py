# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
# Copyright © 2013 eNovance
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
#         Julien Danjou <julien@danjou.info>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""MongoDB storage backend
"""

import calendar
import copy
import operator
import uuid
import weakref

import bson.code
import bson.objectid
import pymongo

from oslo.config import cfg

from ceilometer.openstack.common import log
from ceilometer import storage
from ceilometer.storage import base
from ceilometer.storage import models

cfg.CONF.import_opt('time_to_live', 'ceilometer.storage',
                    group="database")

LOG = log.getLogger(__name__)


class MongoDBStorage(base.StorageEngine):
    """Put the data into a MongoDB database

    Collections::

        - user
          - { _id: user id
              source: [ array of source ids reporting for the user ]
              }
        - project
          - { _id: project id
              source: [ array of source ids reporting for the project ]
              }
        - meter
          - the raw incoming data
        - resource
          - the metadata for resources
          - { _id: uuid of resource,
              metadata: metadata dictionaries
              user_id: uuid
              project_id: uuid
              meter: [ array of {counter_name: string, counter_type: string,
                                 counter_unit: string} ]
            }
    """

    def get_connection(self, conf):
        """Return a Connection instance based on the configuration settings.
        """
        return Connection(conf)


def make_timestamp_range(start, end,
                         start_timestamp_op=None, end_timestamp_op=None):
    """Given two possible datetimes and their operations, create the query
    document to find timestamps within that range.
    By default, using $gte for the lower bound and $lt for the
    upper bound.
    """
    ts_range = {}

    if start:
        if start_timestamp_op == 'gt':
            start_timestamp_op = '$gt'
        else:
            start_timestamp_op = '$gte'
        ts_range[start_timestamp_op] = start

    if end:
        if end_timestamp_op == 'le':
            end_timestamp_op = '$lte'
        else:
            end_timestamp_op = '$lt'
        ts_range[end_timestamp_op] = end
    return ts_range


def make_query_from_filter(sample_filter, require_meter=True):
    """Return a query dictionary based on the settings in the filter.

    :param filter: SampleFilter instance
    :param require_meter: If true and the filter does not have a meter,
                          raise an error.
    """
    q = {}

    if sample_filter.user:
        q['user_id'] = sample_filter.user
    if sample_filter.project:
        q['project_id'] = sample_filter.project

    if sample_filter.meter:
        q['counter_name'] = sample_filter.meter
    elif require_meter:
        raise RuntimeError('Missing required meter specifier')

    ts_range = make_timestamp_range(sample_filter.start, sample_filter.end,
                                    sample_filter.start_timestamp_op,
                                    sample_filter.end_timestamp_op)
    if ts_range:
        q['timestamp'] = ts_range

    if sample_filter.resource:
        q['resource_id'] = sample_filter.resource
    if sample_filter.source:
        q['source'] = sample_filter.source

    # so the samples call metadata resource_metadata, so we convert
    # to that.
    q.update(dict(('resource_%s' % k, v)
                  for (k, v) in sample_filter.metaquery.iteritems()))
    return q


class ConnectionPool(object):

    def __init__(self):
        self._pool = {}

    def connect(self, url):
        if url in self._pool:
            client = self._pool.get(url)()
            if client:
                return client
        LOG.info('connecting to MongoDB on %s', url)
        client = pymongo.MongoClient(
            url,
            use_greenlets=True,
            safe=True)
        self._pool[url] = weakref.ref(client)
        return client


class Connection(base.Connection):
    """MongoDB connection.
    """

    CONNECTION_POOL = ConnectionPool()

    REDUCE_GROUP_CLEAN = bson.code.Code("""
    function ( curr, result ) {
        if (result.resources.indexOf(curr.resource_id) < 0)
            result.resources.push(curr.resource_id);
        if (result.users.indexOf(curr.user_id) < 0)
            result.users.push(curr.user_id);
        if (result.projects.indexOf(curr.project_id) < 0)
            result.projects.push(curr.project_id);
    }
    """)

    MAP_STATS = bson.code.Code("""
    function () {
        emit('statistics', { unit: this.counter_unit,
                             min : this.counter_volume,
                             max : this.counter_volume,
                             sum : this.counter_volume,
                             count : NumberInt(1),
                             duration_start : this.timestamp,
                             duration_end : this.timestamp,
                             period_start : this.timestamp,
                             period_end : this.timestamp} )
    }
    """)

    MAP_STATS_PERIOD = bson.code.Code("""
    function () {
        var period = %d * 1000;
        var period_first = %d * 1000;
        var period_start = period_first
                           + (Math.floor(new Date(this.timestamp.getTime()
                                         - period_first) / period)
                              * period);
        emit(period_start,
             { unit: this.counter_unit,
               min : this.counter_volume,
               max : this.counter_volume,
               sum : this.counter_volume,
               count : NumberInt(1),
               duration_start : this.timestamp,
               duration_end : this.timestamp,
               period_start : new Date(period_start),
               period_end : new Date(period_start + period) } )
    }
    """)

    REDUCE_STATS = bson.code.Code("""
    function (key, values) {
        var res = { unit: values[0].unit,
                    min: values[0].min,
                    max: values[0].max,
                    count: values[0].count,
                    sum: values[0].sum,
                    period_start: values[0].period_start,
                    period_end: values[0].period_end,
                    duration_start: values[0].duration_start,
                    duration_end: values[0].duration_end };
        for ( var i=1; i<values.length; i++ ) {
            if ( values[i].min < res.min )
               res.min = values[i].min;
            if ( values[i].max > res.max )
               res.max = values[i].max;
            res.count = NumberInt(res.count + values[i].count);
            res.sum += values[i].sum;
            if ( values[i].duration_start < res.duration_start )
               res.duration_start = values[i].duration_start;
            if ( values[i].duration_end > res.duration_end )
               res.duration_end = values[i].duration_end;
        }
        return res;
    }
    """)

    FINALIZE_STATS = bson.code.Code("""
    function (key, value) {
        value.avg = value.sum / value.count;
        value.duration = (value.duration_end - value.duration_start) / 1000;
        value.period = NumberInt((value.period_end - value.period_start)
                                  / 1000);
        return value;
    }""")

    def __init__(self, conf):
        url = conf.database.connection

        # NOTE(jd) Use our own connection pooling on top of the Pymongo one.
        # We need that otherwise we overflow the MongoDB instance with new
        # connection since we instanciate a Pymongo client each time someone
        # requires a new storage connection.
        self.conn = self.CONNECTION_POOL.connect(url)

        # Require MongoDB 2.2 to use aggregate() and TTL
        if self.conn.server_info()['versionArray'] < [2, 2]:
            raise storage.StorageBadVersion("Need at least MongoDB 2.2")

        connection_options = pymongo.uri_parser.parse_uri(url)
        self.db = getattr(self.conn, connection_options['database'])

        # NOTE(jd) Upgrading is just about creating index, so let's do this
        # on connection to be sure at least the TTL is correcly updated if
        # needed.
        self.upgrade()

    def upgrade(self):
        # Establish indexes
        #
        # We need variations for user_id vs. project_id because of the
        # way the indexes are stored in b-trees. The user_id and
        # project_id values are usually mutually exclusive in the
        # queries, so the database won't take advantage of an index
        # including both.
        for primary in ['user_id', 'project_id']:
            self.db.resource.ensure_index([
                (primary, pymongo.ASCENDING),
                ('source', pymongo.ASCENDING),
            ], name='resource_idx')
            self.db.meter.ensure_index([
                ('resource_id', pymongo.ASCENDING),
                (primary, pymongo.ASCENDING),
                ('counter_name', pymongo.ASCENDING),
                ('timestamp', pymongo.ASCENDING),
                ('source', pymongo.ASCENDING),
            ], name='meter_idx')
        self.db.meter.ensure_index([('timestamp', pymongo.DESCENDING)],
                                   name='timestamp_idx')

        indexes = self.db.meter.index_information()

        ttl = cfg.CONF.database.time_to_live

        if ttl <= 0:
            if 'meter_ttl' in indexes:
                self.db.meter.drop_index('meter_ttl')
            return

        if 'meter_ttl' in indexes:
            # NOTE(sileht): manually check expireAfterSeconds because
            # ensure_index doesn't update index options if the index already
            # exists
            if ttl == indexes['meter_ttl'].get('expireAfterSeconds', -1):
                return

            self.db.meter.drop_index('meter_ttl')

        self.db.meter.create_index(
            [('timestamp', pymongo.ASCENDING)],
            expireAfterSeconds=ttl,
            name='meter_ttl'
        )

    def clear(self):
        self.conn.drop_database(self.db)
        # Connection will be reopened automatically if needed
        self.conn.close()

    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter
        """
        # Make sure we know about the user and project
        self.db.user.update(
            {'_id': data['user_id']},
            {'$addToSet': {'source': data['source'],
                           },
             },
            upsert=True,
        )
        self.db.project.update(
            {'_id': data['project_id']},
            {'$addToSet': {'source': data['source'],
                           },
             },
            upsert=True,
        )

        # Record the updated resource metadata
        self.db.resource.update(
            {'_id': data['resource_id']},
            {'$set': {'project_id': data['project_id'],
                      'user_id': data['user_id'],
                      'metadata': data['resource_metadata'],
                      'source': data['source'],
                      },
             '$addToSet': {'meter': {'counter_name': data['counter_name'],
                                     'counter_type': data['counter_type'],
                                     'counter_unit': data['counter_unit'],
                                     },
                           },
             },
            upsert=True,
        )

        # Record the raw data for the meter. Use a copy so we do not
        # modify a data structure owned by our caller (the driver adds
        # a new key '_id').
        record = copy.copy(data)
        self.db.meter.insert(record)

    def clear_expired_metering_data(self, ttl):
        """Clear expired data from the backend storage system according to the
        time-to-live.

        :param ttl: Number of seconds to keep records for.

        """
        results = self.db.meter.group(
            key={},
            condition={},
            reduce=self.REDUCE_GROUP_CLEAN,
            initial={
                'resources': [],
                'users': [],
                'projects': [],
            }
        )[0]

        self.db.user.remove({'_id': {'$nin': results['users']}})
        self.db.project.remove({'_id': {'$nin': results['projects']}})
        self.db.resource.remove({'_id': {'$nin': results['resources']}})

    @staticmethod
    def _get_marker(db_collection, marker_pairs):
        """Return the mark document according to the attribute-value pairs.

        :param db_collection: Database collection that be query.
        :param maker_pairs: Attribute-value pairs filter.
        """
        if db_collection is None:
            return
        if not marker_pairs:
            return
        ret = db_collection.find(marker_pairs, limit=2)

        if ret.count() == 0:
            raise base.NoResultFound
        elif ret.count() > 1:
            raise base.MultipleResultsFound
        else:
            _ret = ret.__getitem__(0)
            return _ret

    @classmethod
    def _recurse_sort_keys(cls, sort_keys, marker, flag):
        _first = sort_keys[0]
        value = marker[_first]
        if len(sort_keys) == 1:
            return {_first: {flag: value}}
        else:
            criteria_equ = {_first: {'eq': value}}
            criteria_cmp = cls._recurse_sort_keys(sort_keys[1:], marker, flag)
        return dict(criteria_equ, ** criteria_cmp)

    @classmethod
    def _build_paginate_query(cls, marker, sort_keys=[], sort_dir='desc'):
        """Returns a query with sorting / pagination.

        Pagination works by requiring sort_key and sort_dir.
        We use the last item in previous page as the 'marker' for pagination.
        So we return values that follow the passed marker in the order.
        :param q: The query dict passed in.
        :param marker: the last item of the previous page; we return the next
                       results after this item.
        :param sort_keys: array of attributes by which results be sorted.
        :param sort_dir: direction in which results be sorted (asc, desc).
        :return: sort parameters, query to use
        """
        all_sort = []
        sort_mapping = {'desc': (pymongo.DESCENDING, '$lt'),
                        'asc': (pymongo.ASCENDING, '$gt')
                        }
        _sort_dir, _sort_flag = sort_mapping.get(sort_dir,
                                                 sort_mapping['desc'])

        for _sort_key in sort_keys:
            _all_sort = (_sort_key, _sort_dir)
            all_sort.append(_all_sort)

        if marker is not None:
            sort_criteria_list = []

            for i in range(0, len(sort_keys)):
                sort_criteria_list.append(cls._recurse_sort_keys(
                                          sort_keys[:(len(sort_keys) - i)],
                                          marker, _sort_flag))

            metaquery = {"$or": sort_criteria_list}
        else:
            metaquery = {}

        return all_sort, metaquery

    @classmethod
    def paginate_query(cls, q, db_collection, limit=None, marker=None,
                       sort_keys=[], sort_dir='desc'):
        """Returns a query result with sorting / pagination.

        Pagination works by requiring sort_key and sort_dir.
        We use the last item in previous page as the 'marker' for pagination.
        So we return values that follow the passed marker in the order.
        :param q: the query dict passed in.
        :param db_collection: Database collection that be query.
        :param limit: maximum number of items to return.
        :param marker: the last item of the previous page; we return the next
                       results after this item.
        :param sort_keys: array of attributes by which results be sorted.
        :param sort_dir: direction in which results be sorted (asc, desc).
        return: The query with sorting/pagination added.
        """

        all_sort, query = cls._build_paginate_query(marker,
                                                    sort_keys,
                                                    sort_dir)
        q.update(query)

        #NOTE(Fengqian):MongoDB collection.find can not handle limit
        #when it equals None, it will raise TypeError, so we treate
        #None as 0 for the value of limit.
        if limit is None:
            limit = 0
        return db_collection.find(q, limit=limit, sort=all_sort)

    def get_users(self, source=None):
        """Return an iterable of user id strings.

        :param source: Optional source filter.
        """
        q = {}
        if source is not None:
            q['source'] = source

        return (doc['_id'] for doc in
                self.db.user.find(q, fields=['_id'],
                                  sort=[('_id', pymongo.ASCENDING)]))

    def get_projects(self, source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """
        q = {}
        if source is not None:
            q['source'] = source

        return (doc['_id'] for doc in
                self.db.project.find(q, fields=['_id'],
                                     sort=[('_id', pymongo.ASCENDING)]))

    def get_resources(self, user=None, project=None, source=None,
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None,
                      metaquery={}, resource=None, limit=None,
                      marker_pairs=None, sort_key=None, sort_dir=None):
        """Return an iterable of models.Resource instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param source: Optional source filter.
        :param start_timestamp: Optional modified timestamp start range.
        :param start_timestamp_op: Optional start time operator, like gt, ge.
        :param end_timestamp: Optional modified timestamp end range.
        :param end_timestamp_op: Optional end time operator, like lt, le.
        :param metaquery: Optional dict with metadata to match on.
        :param resource: Optional resource filter.
        :param limit: Number of documents should be returned.
        :param marker_pairs: Attribute-value pairs to identify the last item of
                            the previous page.
        :param sort_key: Attribute by which results be sorted.
        :param sort_dir: Direction with which results be sorted(asc, desc).
        """

        if marker_pairs is not None:
            raise NotImplementedError(
                "Cannot use marker pairs in resource listing")

        q = {}
        if user is not None:
            q['user_id'] = user
        if project is not None:
            q['project_id'] = project
        if source is not None:
            q['source'] = source
        if resource is not None:
            q['resource_id'] = resource
        # Add resource_ prefix so it matches the field in the db
        q.update(dict(('resource_' + k, v)
                      for (k, v) in metaquery.iteritems()))

        # FIXME(dhellmann): This may not perform very well,
        # but doing any better will require changing the database
        # schema and that will need more thought than I have time
        # to put into it today.
        if start_timestamp or end_timestamp:
            # Look for resources matching the above criteria and with
            # samples in the time range we care about, then change the
            # resource query to return just those resources by id.
            ts_range = make_timestamp_range(start_timestamp, end_timestamp,
                                            start_timestamp_op,
                                            end_timestamp_op)
            if ts_range:
                q['timestamp'] = ts_range

        sort_keys = base._handle_sort_key('resource', sort_key)
        sort_instruction, query = self._build_paginate_query(None,
                                                             sort_keys,
                                                             sort_dir)
        q.update(query)

        aggregate = self.db.meter.aggregate([
            {"$match": q},
            {"$sort": dict(sort_instruction)},
            {"$group": {
                "_id": "$resource_id",
                "user_id": {"$first": "$user_id"},
                "project_id": {"$first": "$project_id"},
                "source": {"$first": "$source"},
                "first_sample_timestamp": {"$min": "$timestamp"},
                "last_sample_timestamp": {"$max": "$timestamp"},
                "metadata": {"$first": "$resource_metadata"},
                "meters_name": {"$push": "$counter_name"},
                "meters_type": {"$push": "$counter_type"},
                "meters_unit": {"$push": "$counter_unit"},
            }},
        ])

        for result in aggregate['result']:
            if limit is not None:
                if limit == 0:
                    break
                limit -= 1
            yield models.Resource(
                resource_id=result['_id'],
                user_id=result['user_id'],
                project_id=result['project_id'],
                first_sample_timestamp=result['first_sample_timestamp'],
                last_sample_timestamp=result['last_sample_timestamp'],
                source=result['source'],
                metadata=result['metadata'],
                meter=[
                    models.ResourceMeter(
                        counter_name=m_n,
                        counter_type=m_t,
                        counter_unit=m_u,
                    )
                    for m_n, m_u, m_t in zip(result['meters_name'],
                                             result['meters_unit'],
                                             result['meters_type'])
                ],
            )

    def get_meters(self, user=None, project=None, resource=None, source=None,
                   metaquery={}, limit=None, marker_pairs=None, sort_key=None,
                   sort_dir=None):
        """Return an iterable of models.Meter instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional resource filter.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param limit: Number of documents should be returned.
        :param marker_pairs: Attribute-value pairs to identify the last item of
                             the previous page.
        :param sort_key: Attribute by which results be sorted.
        :param sort_dir: Direction with which results be sorted(asc, desc).
        """
        q = {}
        if user is not None:
            q['user_id'] = user
        if project is not None:
            q['project_id'] = project
        if resource is not None:
            q['_id'] = resource
        if source is not None:
            q['source'] = source
        q.update(metaquery)

        marker = self._get_marker(self.db.resource, marker_pairs=marker_pairs)
        sort_keys = base._handle_sort_key('meter', sort_key)

        for r in self.paginate_query(q, self.db.resource, limit=limit,
                                     marker=marker,
                                     sort_keys=sort_keys, sort_dir=sort_dir):
            for r_meter in r['meter']:
                yield models.Meter(
                    name=r_meter['counter_name'],
                    type=r_meter['counter_type'],
                    # Return empty string if 'counter_unit' is not valid for
                    # backward compatibility.
                    unit=r_meter.get('counter_unit', ''),
                    resource_id=r['_id'],
                    project_id=r['project_id'],
                    source=r['source'],
                    user_id=r['user_id'],
                )

    def get_samples(self, sample_filter, limit=None):
        """Return an iterable of model.Sample instances.

        :param sample_filter: Filter.
        :param limit: Maximum number of results to return.
        """
        if limit == 0:
            return
        q = make_query_from_filter(sample_filter, require_meter=False)
        if limit:
            samples = self.db.meter.find(
                q, limit=limit, sort=[("timestamp", pymongo.DESCENDING)])
        else:
            samples = self.db.meter.find(
                q, sort=[("timestamp", pymongo.DESCENDING)])

        for s in samples:
            # Remove the ObjectId generated by the database when
            # the sample was inserted. It is an implementation
            # detail that should not leak outside of the driver.
            del s['_id']
            # Backward compatibility for samples without units
            s['counter_unit'] = s.get('counter_unit', '')
            yield models.Sample(**s)

    def get_meter_statistics(self, sample_filter, period=None):
        """Return an iterable of models.Statistics instance containing meter
        statistics described by the query parameters.

        The filter must have a meter value set.

        """
        q = make_query_from_filter(sample_filter)

        if period:
            if sample_filter.start:
                period_start = sample_filter.start
            else:
                period_start = self.db.meter.find(
                    limit=1, sort=[('timestamp',
                                    pymongo.ASCENDING)])[0]['timestamp']
            period_start = int(calendar.timegm(period_start.utctimetuple()))
            map_stats = self.MAP_STATS_PERIOD % (period, period_start)
        else:
            map_stats = self.MAP_STATS

        results = self.db.meter.map_reduce(
            map_stats,
            self.REDUCE_STATS,
            {'inline': 1},
            finalize=self.FINALIZE_STATS,
            query=q,
        )

        return sorted((models.Statistics(**(r['value']))
                       for r in results['results']),
                      key=operator.attrgetter('period_start'))

    @staticmethod
    def _decode_matching_metadata(matching_metadata):
        if isinstance(matching_metadata, dict):
            #note(sileht): keep compatibility with old db format
            return matching_metadata
        else:
            new_matching_metadata = {}
            for elem in matching_metadata:
                new_matching_metadata[elem['key']] = elem['value']
            return new_matching_metadata

    @staticmethod
    def _encode_matching_metadata(matching_metadata):
        if matching_metadata:
            new_matching_metadata = []
            for k, v in matching_metadata.iteritems():
                new_matching_metadata.append({'key': k, 'value': v})
            return new_matching_metadata
        return matching_metadata

    def get_alarms(self, name=None, user=None,
                   project=None, enabled=True, alarm_id=None, limit=None,
                   marker_pairs=None, sort_key=None, sort_dir=None):
        """Yields a lists of alarms that match filters
        :param name: The Alarm name.
        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param enabled: Optional boolean to list disable alarm.
        :param alarm_id: Optional alarm_id to return one alarm.
        :param limit: Number of rows should be returned.
        :param marker_pairs: Attribute-value pairs to identify the last item of
                            the previous page.
        :param sort_key: Attribute by which results be sorted.
        :param sort_dir: Direction with which results be sorted(asc, desc).
        """
        q = {}
        if user is not None:
            q['user_id'] = user
        if project is not None:
            q['project_id'] = project
        if name is not None:
            q['name'] = name
        if enabled is not None:
            q['enabled'] = enabled
        if alarm_id is not None:
            q['alarm_id'] = alarm_id

        marker = self._get_marker(self.db.alarm, marker_pairs=marker_pairs)
        sort_keys = base._handle_sort_key('alarm', sort_key)

        for alarm in self.paginate_query(q, self.db.alarm, limit=limit,
                                         marker=marker, sort_keys=sort_keys,
                                         sort_dir=sort_dir):
            a = {}
            a.update(alarm)
            del a['_id']
            a['matching_metadata'] = \
                self._decode_matching_metadata(a['matching_metadata'])
            yield models.Alarm(**a)

    def update_alarm(self, alarm):
        """update alarm
        """
        if alarm.alarm_id is None:
            # This is an insert, generate an id
            alarm.alarm_id = str(uuid.uuid1())
        data = alarm.as_dict()
        data['matching_metadata'] = \
            self._encode_matching_metadata(data['matching_metadata'])

        self.db.alarm.update(
            {'alarm_id': alarm.alarm_id},
            {'$set': data},
            upsert=True)

        stored_alarm = self.db.alarm.find({'alarm_id': alarm.alarm_id})[0]
        del stored_alarm['_id']
        stored_alarm['matching_metadata'] = \
            self._decode_matching_metadata(stored_alarm['matching_metadata'])
        return models.Alarm(**stored_alarm)

    def delete_alarm(self, alarm_id):
        """Delete a alarm
        """
        self.db.alarm.remove({'alarm_id': alarm_id})

    @staticmethod
    def record_events(events):
        """Write the events.

        :param events: a list of model.Event objects.
        """
        raise NotImplementedError('Events not implemented.')

    @staticmethod
    def get_events(event_filter):
        """Return an iterable of model.Event objects.

        :param event_filter: EventFilter instance
        """
        raise NotImplementedError('Events not implemented.')
