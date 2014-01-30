# -*- encoding: utf-8 -*-
# Copyright © 2012 New Dream Network, LLC (DreamHost)
# Copyright © 2013 eNovance
# Copyright © 2013 IBM Corp
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
#         Julien Danjou <julien@danjou.info>
#         Tong Li <litong01@us.ibm.com>
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
"""DB2 storage backend
"""

from __future__ import division
import copy
import datetime
import itertools
import sys
import weakref

import bson.code
import bson.objectid
import pymongo

from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer import storage
from ceilometer.storage import base
from ceilometer.storage import models

LOG = log.getLogger(__name__)


class DB2Storage(base.StorageEngine):
    """The db2 storage for Ceilometer

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
    if sample_filter.message_id:
        q['message_id'] = sample_filter.message_id

    # so the samples call metadata resource_metadata, so we convert
    # to that.
    q.update(dict(('resource_%s' % k, v)
                  for (k, v) in sample_filter.metaquery.iteritems()))
    return q


class ConnectionPool(object):

    def __init__(self):
        self._pool = {}

    def connect(self, url):
        connection_options = pymongo.uri_parser.parse_uri(url)
        del connection_options['database']
        del connection_options['username']
        del connection_options['password']
        del connection_options['collection']
        pool_key = tuple(connection_options)

        if pool_key in self._pool:
            client = self._pool.get(pool_key)()
            if client:
                return client
        LOG.info(_('Connecting to DB2 on %s'),
                 connection_options['nodelist'])
        client = pymongo.MongoClient(
            url,
            safe=True)
        self._pool[pool_key] = weakref.ref(client)
        return client


class Connection(base.Connection):
    """DB2 connection.
    """

    CONNECTION_POOL = ConnectionPool()

    GROUP = {'_id': '$counter_name',
             'unit': {'$min': '$counter_unit'},
             'min': {'$min': '$counter_volume'},
             'max': {'$max': '$counter_volume'},
             'sum': {'$sum': '$counter_volume'},
             'count': {'$sum': 1},
             'duration_start': {'$min': '$timestamp'},
             'duration_end': {'$max': '$timestamp'},
             }

    PROJECT = {'_id': 0, 'unit': 1,
               'min': 1, 'max': 1, 'sum': 1, 'count': 1,
               'avg': {'$divide': ['$sum', '$count']},
               'duration_start': 1,
               'duration_end': 1,
               }

    SORT_OPERATION_MAP = {'desc': pymongo.DESCENDING, 'asc': pymongo.ASCENDING}

    SECONDS_IN_A_DAY = 86400

    def __init__(self, conf):
        url = conf.database.connection

        # Since we are using pymongo, even though we are connecting to DB2
        # we still have to make sure that the scheme which used to distinguish
        # db2 driver from mongodb driver be replaced so that pymongo will not
        # produce an exception on the scheme.
        url = url.replace('db2:', 'mongodb:', 1)
        self.conn = self.CONNECTION_POOL.connect(url)

        # Require MongoDB 2.2 to use aggregate(), since we are using mongodb
        # as backend for test, the following code is necessary to make sure
        # that the test wont try aggregate on older mongodb during the test.
        # For db2, the versionArray won't be part of the server_info, so there
        # will not be exception when real db2 gets used as backend.
        server_info = self.conn.server_info()
        if server_info.get('sysInfo'):
            self._using_mongodb = True
        else:
            self._using_mongodb = False

        if self._using_mongodb and server_info.get('versionArray') < [2, 2]:
            raise storage.StorageBadVersion("Need at least MongoDB 2.2")

        connection_options = pymongo.uri_parser.parse_uri(url)
        self.db = getattr(self.conn, connection_options['database'])
        if connection_options.get('username'):
            self.db.authenticate(connection_options['username'],
                                 connection_options['password'])

        self.upgrade()

    @classmethod
    def _build_sort_instructions(cls, sort_keys=[], sort_dir='desc'):
        """Returns a sort_instruction.

        Sort instructions are used in the query to determine what attributes
        to sort on and what direction to use.
        :param q: The query dict passed in.
        :param sort_keys: array of attributes by which results be sorted.
        :param sort_dir: direction in which results be sorted (asc, desc).
        :return: sort parameters
        """
        sort_instructions = []
        _sort_dir = cls.SORT_OPERATION_MAP.get(
            sort_dir, cls.SORT_OPERATION_MAP['desc'])

        for _sort_key in sort_keys:
            _instruction = (_sort_key, _sort_dir)
            sort_instructions.append(_instruction)

        return sort_instructions

    def upgrade(self, version=None):
        # Establish indexes
        #
        # We need variations for user_id vs. project_id because of the
        # way the indexes are stored in b-trees. The user_id and
        # project_id values are usually mutually exclusive in the
        # queries, so the database won't take advantage of an index
        # including both.
        if self.db.resource.index_information() == {}:
            resource_id = str(bson.objectid.ObjectId())
            self.db.resource.insert({'_id': resource_id,
                                     'no_key': resource_id})
            meter_id = str(bson.objectid.ObjectId())
            self.db.meter.insert({'_id': meter_id,
                                  'no_key': meter_id})

            self.db.resource.ensure_index([
                ('user_id', pymongo.ASCENDING),
                ('project_id', pymongo.ASCENDING),
                ('source', pymongo.ASCENDING)], name='resource_idx')

            self.db.meter.ensure_index([
                ('resource_id', pymongo.ASCENDING),
                ('user_id', pymongo.ASCENDING),
                ('project_id', pymongo.ASCENDING),
                ('counter_name', pymongo.ASCENDING),
                ('timestamp', pymongo.ASCENDING),
                ('source', pymongo.ASCENDING)], name='meter_idx')

            self.db.meter.ensure_index([('timestamp',
                                         pymongo.DESCENDING)],
                                       name='timestamp_idx')

            self.db.resource.remove({'_id': resource_id})
            self.db.meter.remove({'_id': meter_id})

            # The following code is to ensure that the keys for collections
            # are set as objectId so that db2 index on key can be created
            # correctly
            user_id = str(bson.objectid.ObjectId())
            self.db.user.insert({'_id': user_id})
            self.db.user.remove({'_id': user_id})

            project_id = str(bson.objectid.ObjectId())
            self.db.project.insert({'_id': project_id})
            self.db.project.remove({'_id': project_id})

    def clear(self):
        # db2 does not support drop_database, remove all collections
        for col in ['user', 'project', 'resource', 'meter']:
            self.db[col].drop()
        # drop_database command does nothing on db2 database since this has
        # not been implemented. However calling this method is important for
        # removal of all the empty dbs created during the test runs since
        # test run is against mongodb on Jenkins
        self.conn.drop_database(self.db)
        self.conn.close()

    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter
        """
        # Make sure we know about the user and project
        self.db.user.update(
            {'_id': data['user_id'] or 'null'},
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
                      'user_id': data['user_id'] or 'null',
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
        record['recorded_at'] = timeutils.utcnow()
        # Make sure that the data does have field _id which db2 wont add
        # automatically.
        if record.get('_id') is None:
            record['_id'] = str(bson.objectid.ObjectId())
        self.db.meter.insert(record)

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
                      metaquery={}, resource=None, pagination=None):
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
        :param pagination: Optional pagination query.
        """
        if pagination:
            raise NotImplementedError(_('Pagination not implemented'))

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

        if start_timestamp or end_timestamp:
            # Look for resources matching the above criteria and with
            # samples in the time range we care about, then change the
            # resource query to return just those resources by id.
            ts_range = make_timestamp_range(start_timestamp, end_timestamp,
                                            start_timestamp_op,
                                            end_timestamp_op)
            if ts_range:
                q['timestamp'] = ts_range

        sort_keys = base._handle_sort_key('resource', 'timestamp')
        sort_keys.insert(0, 'resource_id')
        sort_instructions = self._build_sort_instructions(sort_keys=sort_keys,
                                                          sort_dir='desc')
        resource = lambda x: x['resource_id']
        meters = self.db.meter.find(q, sort=sort_instructions)
        for resource_id, r_meters in itertools.groupby(meters, key=resource):
            # Because we have to know first/last timestamp, and we need a full
            # list of references to the resource's meters, we need a tuple
            # here.
            r_meters = tuple(r_meters)
            latest_meter = r_meters[0]
            last_ts = latest_meter['timestamp']
            first_ts = r_meters[-1]['timestamp']

            yield models.Resource(resource_id=latest_meter['resource_id'],
                                  project_id=latest_meter['project_id'],
                                  first_sample_timestamp=first_ts,
                                  last_sample_timestamp=last_ts,
                                  source=latest_meter['source'],
                                  user_id=latest_meter['user_id'],
                                  metadata=latest_meter['resource_metadata'])

    def get_meters(self, user=None, project=None, resource=None, source=None,
                   metaquery={}, pagination=None):
        """Return an iterable of models.Meter instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional resource filter.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param pagination: Optional pagination query.
        """

        if pagination:
            raise NotImplementedError(_('Pagination not implemented'))

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

        for r in self.db.resource.find(q):
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

    def get_meter_statistics(self, sample_filter, period=None, groupby=None):
        """Return an iterable of models.Statistics instance containing meter
        statistics described by the query parameters.

        The filter must have a meter value set.
        """
        if (groupby and
                set(groupby) - set(['user_id', 'project_id',
                                    'resource_id', 'source'])):
            raise NotImplementedError("Unable to group by these fields")

        q = make_query_from_filter(sample_filter)

        if period:
            if sample_filter.start:
                period_start = sample_filter.start
            else:
                period_start = self.db.meter.find(
                    limit=1, sort=[('timestamp',
                                    pymongo.ASCENDING)])[0]['timestamp']

        if groupby:
            sort_keys = ['counter_name'] + groupby + ['timestamp']
        else:
            sort_keys = ['counter_name', 'timestamp']

        sort_instructions = self._build_sort_instructions(sort_keys=sort_keys,
                                                          sort_dir='asc')
        meters = self.db.meter.find(q, sort=sort_instructions)

        def _group_key(meter):
            # the method to define a key for groupby call
            key = {}
            for y in sort_keys:
                if y == 'timestamp' and period:
                    key[y] = (timeutils.delta_seconds(period_start,
                                                      meter[y]) // period)
                elif y != 'timestamp':
                    key[y] = meter[y]
            return key

        def _to_offset(periods):
            return {'days': (periods * period) // self.SECONDS_IN_A_DAY,
                    'seconds': (periods * period) % self.SECONDS_IN_A_DAY}

        for key, grouped_meters in itertools.groupby(meters, key=_group_key):
            stat = models.Statistics(None, sys.maxint, -sys.maxint, 0, 0, 0,
                                     0, 0, 0, 0, 0, 0, None)

            for meter in grouped_meters:
                stat.unit = meter.get('counter_unit', '')
                m_volume = meter.get('counter_volume')
                if stat.min > m_volume:
                    stat.min = m_volume
                if stat.max < m_volume:
                    stat.max = m_volume
                stat.sum += m_volume
                stat.count += 1
                if stat.duration_start == 0:
                    stat.duration_start = meter['timestamp']
                stat.duration_end = meter['timestamp']
                if groupby and not stat.groupby:
                    stat.groupby = {}
                    for group_key in groupby:
                        stat.groupby[group_key] = meter[group_key]

            stat.duration = timeutils.delta_seconds(stat.duration_start,
                                                    stat.duration_end)
            stat.avg = stat.sum / stat.count
            if period:
                stat.period = period
                periods = key.get('timestamp')
                stat.period_start = period_start + \
                    datetime.timedelta(**(_to_offset(periods)))
                stat.period_end = period_start + \
                    datetime.timedelta(**(_to_offset(periods + 1)))
            else:
                stat.period_start = stat.duration_start
                stat.period_end = stat.duration_end
            yield stat

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

    @classmethod
    def _ensure_encapsulated_rule_format(cls, alarm):
        """This ensure the alarm returned by the storage have the correct
        format. The previous format looks like:
        {
            'alarm_id': '0ld-4l3rt',
            'enabled': True,
            'name': 'old-alert',
            'description': 'old-alert',
            'timestamp': None,
            'meter_name': 'cpu',
            'user_id': 'me',
            'project_id': 'and-da-boys',
            'comparison_operator': 'lt',
            'threshold': 36,
            'statistic': 'count',
            'evaluation_periods': 1,
            'period': 60,
            'state': "insufficient data",
            'state_timestamp': None,
            'ok_actions': [],
            'alarm_actions': ['http://nowhere/alarms'],
            'insufficient_data_actions': [],
            'repeat_actions': False,
            'matching_metadata': {'key': 'value'}
            # or 'matching_metadata': [{'key': 'key', 'value': 'value'}]
        }
        """

        if isinstance(alarm.get('rule'), dict):
            return

        alarm['type'] = 'threshold'
        alarm['rule'] = {}
        alarm['matching_metadata'] = cls._decode_matching_metadata(
            alarm['matching_metadata'])
        for field in ['period', 'evaluation_period', 'threshold',
                      'statistic', 'comparison_operator', 'meter_name']:
            if field in alarm:
                alarm['rule'][field] = alarm[field]
                del alarm[field]

        query = []
        for key in alarm['matching_metadata']:
            query.append({'field': key,
                          'op': 'eq',
                          'value': alarm['matching_metadata'][key]})
        del alarm['matching_metadata']
        alarm['rule']['query'] = query

    def get_alarms(self, name=None, user=None,
                   project=None, enabled=None, alarm_id=None, pagination=None):
        """Yields a lists of alarms that match filters
        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param enabled: Optional boolean to list disable alarm.
        :param alarm_id: Optional alarm_id to return one alarm.
        :param metaquery: Optional dict with metadata to match on.
        :param resource: Optional resource filter.
        :param pagination: Optional pagination query.
        """

        if pagination:
            raise NotImplementedError(_('Pagination not implemented'))

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

        for alarm in self.db.alarm.find(q):
            a = {}
            a.update(alarm)
            del a['_id']
            self._ensure_encapsulated_rule_format(a)
            yield models.Alarm(**a)

    def update_alarm(self, alarm):
        """update alarm
        """
        data = alarm.as_dict()
        self.db.alarm.update(
            {'alarm_id': alarm.alarm_id},
            {'$set': data},
            upsert=True)

        stored_alarm = self.db.alarm.find({'alarm_id': alarm.alarm_id})[0]
        del stored_alarm['_id']
        self._ensure_encapsulated_rule_format(stored_alarm)
        return models.Alarm(**stored_alarm)

    create_alarm = update_alarm

    def delete_alarm(self, alarm_id):
        """Delete an alarm
        """
        self.db.alarm.remove({'alarm_id': alarm_id})
