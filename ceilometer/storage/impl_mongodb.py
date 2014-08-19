#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 eNovance
# Copyright 2014 Red Hat, Inc
#
# Authors: Doug Hellmann <doug.hellmann@dreamhost.com>
#          Julien Danjou <julien@danjou.info>
#          Eoghan Glynn <eglynn@redhat.com>
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
"""MongoDB storage backend"""

import calendar
import copy
import datetime
import json
import operator
import uuid

import bson.code
import bson.objectid
from oslo.config import cfg
from oslo.utils import timeutils
import pymongo
import six

from ceilometer.openstack.common import log
from ceilometer import storage
from ceilometer.storage import base
from ceilometer.storage import models
from ceilometer.storage.mongo import utils as pymongo_utils
from ceilometer.storage import pymongo_base
from ceilometer import utils

cfg.CONF.import_opt('time_to_live', 'ceilometer.storage',
                    group="database")

LOG = log.getLogger(__name__)


AVAILABLE_CAPABILITIES = {
    'resources': {'query': {'simple': True,
                            'metadata': True}},
    'statistics': {'groupby': True,
                   'query': {'simple': True,
                             'metadata': True},
                   'aggregation': {'standard': True,
                                   'selectable': {'max': True,
                                                  'min': True,
                                                  'sum': True,
                                                  'avg': True,
                                                  'count': True,
                                                  'stddev': True,
                                                  'cardinality': True}}}
}


class Connection(pymongo_base.Connection):
    """Put the data into a MongoDB database

    Collections::

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

    CAPABILITIES = utils.update_nested(pymongo_base.Connection.CAPABILITIES,
                                       AVAILABLE_CAPABILITIES)
    CONNECTION_POOL = pymongo_utils.ConnectionPool()

    REDUCE_GROUP_CLEAN = bson.code.Code("""
    function ( curr, result ) {
        if (result.resources.indexOf(curr.resource_id) < 0)
            result.resources.push(curr.resource_id);
    }
    """)

    STANDARD_AGGREGATES = dict(
        emit_initial=dict(
            sum='',
            count='',
            avg='',
            min='',
            max=''
        ),
        emit_body=dict(
            sum='sum: this.counter_volume,',
            count='count: NumberInt(1),',
            avg='acount: NumberInt(1), asum: this.counter_volume,',
            min='min: this.counter_volume,',
            max='max: this.counter_volume,'
        ),
        reduce_initial=dict(
            sum='',
            count='',
            avg='',
            min='',
            max=''
        ),
        reduce_body=dict(
            sum='sum: values[0].sum,',
            count='count: values[0].count,',
            avg='acount: values[0].acount, asum: values[0].asum,',
            min='min: values[0].min,',
            max='max: values[0].max,'
        ),
        reduce_computation=dict(
            sum='res.sum += values[i].sum;',
            count='res.count = NumberInt(res.count + values[i].count);',
            avg=('res.acount = NumberInt(res.acount + values[i].acount);'
                 'res.asum += values[i].asum;'),
            min='if ( values[i].min < res.min ) {res.min = values[i].min;}',
            max='if ( values[i].max > res.max ) {res.max = values[i].max;}'
        ),
        finalize=dict(
            sum='',
            count='',
            avg='value.avg = value.asum / value.acount;',
            min='',
            max=''
        ),
    )

    UNPARAMETERIZED_AGGREGATES = dict(
        emit_initial=dict(
            stddev=(
                ''
            )
        ),
        emit_body=dict(
            stddev='sdsum: this.counter_volume,'
                   'sdcount: 1,'
                   'weighted_distances: 0,'
                   'stddev: 0,'
        ),
        reduce_initial=dict(
            stddev=''
        ),
        reduce_body=dict(
            stddev='sdsum: values[0].sdsum,'
                   'sdcount: values[0].sdcount,'
                   'weighted_distances: values[0].weighted_distances,'
                   'stddev: values[0].stddev,'
        ),
        reduce_computation=dict(
            stddev=(
                'var deviance = (res.sdsum / res.sdcount) - values[i].sdsum;'
                'var weight = res.sdcount / ++res.sdcount;'
                'res.weighted_distances += (Math.pow(deviance, 2) * weight);'
                'res.sdsum += values[i].sdsum;'
            )
        ),
        finalize=dict(
            stddev=(
                'value.stddev = Math.sqrt(value.weighted_distances /'
                '  value.sdcount);'
            )
        ),
    )

    PARAMETERIZED_AGGREGATES = dict(
        validate=dict(
            cardinality=lambda p: p in ['resource_id', 'user_id', 'project_id',
                                        'source']
        ),
        emit_initial=dict(
            cardinality=(
                'aggregate["cardinality/%(aggregate_param)s"] = 1;'
                'var distinct_%(aggregate_param)s = {};'
                'distinct_%(aggregate_param)s[this["%(aggregate_param)s"]]'
                '   = true;'
            )
        ),
        emit_body=dict(
            cardinality=(
                'distinct_%(aggregate_param)s : distinct_%(aggregate_param)s,'
                '%(aggregate_param)s : this["%(aggregate_param)s"],'
            )
        ),
        reduce_initial=dict(
            cardinality=''
        ),
        reduce_body=dict(
            cardinality=(
                'aggregate : values[0].aggregate,'
                'distinct_%(aggregate_param)s:'
                '  values[0].distinct_%(aggregate_param)s,'
                '%(aggregate_param)s : values[0]["%(aggregate_param)s"],'
            )
        ),
        reduce_computation=dict(
            cardinality=(
                'if (!(values[i]["%(aggregate_param)s"] in'
                '      res.distinct_%(aggregate_param)s)) {'
                '  res.distinct_%(aggregate_param)s[values[i]'
                '    ["%(aggregate_param)s"]] = true;'
                '  res.aggregate["cardinality/%(aggregate_param)s"] += 1;}'
            )
        ),
        finalize=dict(
            cardinality=''
        ),
    )

    EMIT_STATS_COMMON = """
        var aggregate = {};
        %(aggregate_initial_placeholder)s
        emit(%(key_val)s, { unit: this.counter_unit,
                            aggregate : aggregate,
                            %(aggregate_body_placeholder)s
                            groupby : %(groupby_val)s,
                            duration_start : this.timestamp,
                            duration_end : this.timestamp,
                            period_start : %(period_start_val)s,
                            period_end : %(period_end_val)s} )
    """

    MAP_STATS_PERIOD_VAR = """
        var period = %(period)d * 1000;
        var period_first = %(period_first)d * 1000;
        var period_start = period_first
                           + (Math.floor(new Date(this.timestamp.getTime()
                                         - period_first) / period)
                              * period);
    """

    MAP_STATS_GROUPBY_VAR = """
        var groupby_fields = %(groupby_fields)s;
        var groupby = {};
        var groupby_key = {};

        for ( var i=0; i<groupby_fields.length; i++ ) {
            groupby[groupby_fields[i]] = this[groupby_fields[i]]
            groupby_key[groupby_fields[i]] = this[groupby_fields[i]]
        }
    """

    PARAMS_MAP_STATS = {
        'key_val': '\'statistics\'',
        'groupby_val': 'null',
        'period_start_val': 'this.timestamp',
        'period_end_val': 'this.timestamp',
        'aggregate_initial_placeholder': '%(aggregate_initial_val)s',
        'aggregate_body_placeholder': '%(aggregate_body_val)s'
    }

    MAP_STATS = bson.code.Code("function () {" +
                               EMIT_STATS_COMMON % PARAMS_MAP_STATS +
                               "}")

    PARAMS_MAP_STATS_PERIOD = {
        'key_val': 'period_start',
        'groupby_val': 'null',
        'period_start_val': 'new Date(period_start)',
        'period_end_val': 'new Date(period_start + period)',
        'aggregate_initial_placeholder': '%(aggregate_initial_val)s',
        'aggregate_body_placeholder': '%(aggregate_body_val)s'
    }

    MAP_STATS_PERIOD = bson.code.Code(
        "function () {" +
        MAP_STATS_PERIOD_VAR +
        EMIT_STATS_COMMON % PARAMS_MAP_STATS_PERIOD +
        "}")

    PARAMS_MAP_STATS_GROUPBY = {
        'key_val': 'groupby_key',
        'groupby_val': 'groupby',
        'period_start_val': 'this.timestamp',
        'period_end_val': 'this.timestamp',
        'aggregate_initial_placeholder': '%(aggregate_initial_val)s',
        'aggregate_body_placeholder': '%(aggregate_body_val)s'
    }

    MAP_STATS_GROUPBY = bson.code.Code(
        "function () {" +
        MAP_STATS_GROUPBY_VAR +
        EMIT_STATS_COMMON % PARAMS_MAP_STATS_GROUPBY +
        "}")

    PARAMS_MAP_STATS_PERIOD_GROUPBY = {
        'key_val': 'groupby_key',
        'groupby_val': 'groupby',
        'period_start_val': 'new Date(period_start)',
        'period_end_val': 'new Date(period_start + period)',
        'aggregate_initial_placeholder': '%(aggregate_initial_val)s',
        'aggregate_body_placeholder': '%(aggregate_body_val)s'
    }

    MAP_STATS_PERIOD_GROUPBY = bson.code.Code(
        "function () {" +
        MAP_STATS_PERIOD_VAR +
        MAP_STATS_GROUPBY_VAR +
        "    groupby_key['period_start'] = period_start\n" +
        EMIT_STATS_COMMON % PARAMS_MAP_STATS_PERIOD_GROUPBY +
        "}")

    REDUCE_STATS = bson.code.Code("""
    function (key, values) {
        %(aggregate_initial_val)s
        var res = { unit: values[0].unit,
                    aggregate: values[0].aggregate,
                    %(aggregate_body_val)s
                    groupby: values[0].groupby,
                    period_start: values[0].period_start,
                    period_end: values[0].period_end,
                    duration_start: values[0].duration_start,
                    duration_end: values[0].duration_end };
        for ( var i=1; i<values.length; i++ ) {
            %(aggregate_computation_val)s
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
        %(aggregate_val)s
        value.duration = (value.duration_end - value.duration_start) / 1000;
        value.period = NumberInt((value.period_end - value.period_start)
                                  / 1000);
        return value;
    }""")

    SORT_OPERATION_MAPPING = {'desc': (pymongo.DESCENDING, '$lt'),
                              'asc': (pymongo.ASCENDING, '$gt')}

    MAP_RESOURCES = bson.code.Code("""
    function () {
        emit(this.resource_id,
             {user_id: this.user_id,
              project_id: this.project_id,
              source: this.source,
              first_timestamp: this.timestamp,
              last_timestamp: this.timestamp,
              metadata: this.resource_metadata})
    }""")

    REDUCE_RESOURCES = bson.code.Code("""
    function (key, values) {
        var merge = {user_id: values[0].user_id,
                     project_id: values[0].project_id,
                     source: values[0].source,
                     first_timestamp: values[0].first_timestamp,
                     last_timestamp: values[0].last_timestamp,
                     metadata: values[0].metadata}
        values.forEach(function(value) {
            if (merge.first_timestamp - value.first_timestamp > 0) {
                merge.first_timestamp = value.first_timestamp;
                merge.user_id = value.user_id;
                merge.project_id = value.project_id;
                merge.source = value.source;
            } else if (merge.last_timestamp - value.last_timestamp <= 0) {
                merge.last_timestamp = value.last_timestamp;
                merge.metadata = value.metadata;
            }
        });
        return merge;
      }""")

    _GENESIS = datetime.datetime(year=datetime.MINYEAR, month=1, day=1)
    _APOCALYPSE = datetime.datetime(year=datetime.MAXYEAR, month=12, day=31,
                                    hour=23, minute=59, second=59)

    def __init__(self, url):

        # NOTE(jd) Use our own connection pooling on top of the Pymongo one.
        # We need that otherwise we overflow the MongoDB instance with new
        # connection since we instanciate a Pymongo client each time someone
        # requires a new storage connection.
        self.conn = self.CONNECTION_POOL.connect(url)

        # Require MongoDB 2.4 to use $setOnInsert
        if self.conn.server_info()['versionArray'] < [2, 4]:
            raise storage.StorageBadVersion("Need at least MongoDB 2.4")

        connection_options = pymongo.uri_parser.parse_uri(url)
        self.db = getattr(self.conn, connection_options['database'])
        if connection_options.get('username'):
            self.db.authenticate(connection_options['username'],
                                 connection_options['password'])

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
        name_qualifier = dict(user_id='', project_id='project_')
        background = dict(user_id=False, project_id=True)
        for primary in ['user_id', 'project_id']:
            name = 'resource_%sidx' % name_qualifier[primary]
            self.db.resource.ensure_index([
                (primary, pymongo.ASCENDING),
                ('source', pymongo.ASCENDING),
            ], name=name, background=background[primary])

            name = 'meter_%sidx' % name_qualifier[primary]
            self.db.meter.ensure_index([
                ('resource_id', pymongo.ASCENDING),
                (primary, pymongo.ASCENDING),
                ('counter_name', pymongo.ASCENDING),
                ('timestamp', pymongo.ASCENDING),
                ('source', pymongo.ASCENDING),
            ], name=name, background=background[primary])

        self.db.resource.ensure_index([('last_sample_timestamp',
                                        pymongo.DESCENDING)],
                                      name='last_sample_timestamp_idx',
                                      sparse=True)
        self.db.meter.ensure_index([('timestamp', pymongo.DESCENDING)],
                                   name='timestamp_idx')
        # remove API v1 related table
        self.db.user.drop()
        self.db.project.drop()

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
        # Record the updated resource metadata - we use $setOnInsert to
        # unconditionally insert sample timestamps and resource metadata
        # (in the update case, this must be conditional on the sample not
        # being out-of-order)
        resource = self.db.resource.find_and_modify(
            {'_id': data['resource_id']},
            {'$set': {'project_id': data['project_id'],
                      'user_id': data['user_id'],
                      'source': data['source'],
                      },
             '$setOnInsert': {'metadata': data['resource_metadata'],
                              'first_sample_timestamp': data['timestamp'],
                              'last_sample_timestamp': data['timestamp'],
                              },
             '$addToSet': {'meter': {'counter_name': data['counter_name'],
                                     'counter_type': data['counter_type'],
                                     'counter_unit': data['counter_unit'],
                                     },
                           },
             },
            upsert=True,
            new=True,
        )

        # only update last sample timestamp if actually later (the usual
        # in-order case)
        last_sample_timestamp = resource.get('last_sample_timestamp')
        if (last_sample_timestamp is None or
                last_sample_timestamp <= data['timestamp']):
            self.db.resource.update(
                {'_id': data['resource_id']},
                {'$set': {'metadata': data['resource_metadata'],
                          'last_sample_timestamp': data['timestamp']}}
            )

        # only update first sample timestamp if actually earlier (the unusual
        # out-of-order case)
        # NOTE: a null first sample timestamp is not updated as this indicates
        # a pre-existing resource document dating from before we started
        # recording these timestamps in the resource collection
        first_sample_timestamp = resource.get('first_sample_timestamp')
        if (first_sample_timestamp is not None and
                first_sample_timestamp > data['timestamp']):
            self.db.resource.update(
                {'_id': data['resource_id']},
                {'$set': {'first_sample_timestamp': data['timestamp']}}
            )

        # Record the raw data for the meter. Use a copy so we do not
        # modify a data structure owned by our caller (the driver adds
        # a new key '_id').
        record = copy.copy(data)
        record['recorded_at'] = timeutils.utcnow()
        self.db.meter.insert(record)

    def clear_expired_metering_data(self, ttl):
        """Clear expired data from the backend storage system.

        Clearing occurs according to the time-to-live.
        :param ttl: Number of seconds to keep records for.
        """
        results = self.db.meter.group(
            key={},
            condition={},
            reduce=self.REDUCE_GROUP_CLEAN,
            initial={
                'resources': [],
            }
        )[0]

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
    def _build_paginate_query(cls, marker, sort_keys=None, sort_dir='desc'):
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
        sort_keys = sort_keys or []
        all_sort, _op = cls._build_sort_instructions(sort_keys, sort_dir)

        if marker is not None:
            sort_criteria_list = []

            for i in range(len(sort_keys)):
                # NOTE(fengqian): Generate the query criteria recursively.
                # sort_keys=[k1, k2, k3], maker_value=[v1, v2, v3]
                # sort_flags = ['$lt', '$gt', 'lt'].
                # The query criteria should be
                # {'k3': {'$lt': 'v3'}, 'k2': {'eq': 'v2'}, 'k1':
                #     {'eq': 'v1'}},
                # {'k2': {'$gt': 'v2'}, 'k1': {'eq': 'v1'}},
                # {'k1': {'$lt': 'v1'}} with 'OR' operation.
                # Each recurse will generate one items of three.
                sort_criteria_list.append(cls._recurse_sort_keys(
                                          sort_keys[:(len(sort_keys) - i)],
                                          marker, _op))

            metaquery = {"$or": sort_criteria_list}
        else:
            metaquery = {}

        return all_sort, metaquery

    @classmethod
    def _build_sort_instructions(cls, sort_keys=None, sort_dir='desc'):
        """Returns a sort_instruction and paging operator.

        Sort instructions are used in the query to determine what attributes
        to sort on and what direction to use.
        :param q: The query dict passed in.
        :param sort_keys: array of attributes by which results be sorted.
        :param sort_dir: direction in which results be sorted (asc, desc).
        :return: sort instructions and paging operator
        """
        sort_keys = sort_keys or []
        sort_instructions = []
        _sort_dir, operation = cls.SORT_OPERATION_MAPPING.get(
            sort_dir, cls.SORT_OPERATION_MAPPING['desc'])

        for _sort_key in sort_keys:
            _instruction = (_sort_key, _sort_dir)
            sort_instructions.append(_instruction)

        return sort_instructions, operation

    @classmethod
    def paginate_query(cls, q, db_collection, limit=None, marker=None,
                       sort_keys=None, sort_dir='desc'):
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

        :return: The query with sorting/pagination added.
        """

        sort_keys = sort_keys or []
        all_sort, query = cls._build_paginate_query(marker,
                                                    sort_keys,
                                                    sort_dir)
        q.update(query)

        # NOTE(Fengqian): MongoDB collection.find can not handle limit
        # when it equals None, it will raise TypeError, so we treat
        # None as 0 for the value of limit.
        if limit is None:
            limit = 0
        return db_collection.find(q, limit=limit, sort=all_sort)

    def _get_time_constrained_resources(self, query,
                                        start_timestamp, start_timestamp_op,
                                        end_timestamp, end_timestamp_op,
                                        metaquery, resource):
        """Return an iterable of models.Resource instances

        Items are constrained by sample timestamp.
        :param query: project/user/source query
        :param start_timestamp: modified timestamp start range.
        :param start_timestamp_op: start time operator, like gt, ge.
        :param end_timestamp: modified timestamp end range.
        :param end_timestamp_op: end time operator, like lt, le.
        :param metaquery: dict with metadata to match on.
        :param resource: resource filter.
        """
        if resource is not None:
            query['resource_id'] = resource

        # Add resource_ prefix so it matches the field in the db
        query.update(dict(('resource_' + k, v)
                          for (k, v) in six.iteritems(metaquery)))

        # FIXME(dhellmann): This may not perform very well,
        # but doing any better will require changing the database
        # schema and that will need more thought than I have time
        # to put into it today.
        # Look for resources matching the above criteria and with
        # samples in the time range we care about, then change the
        # resource query to return just those resources by id.
        ts_range = pymongo_utils.make_timestamp_range(start_timestamp,
                                                      end_timestamp,
                                                      start_timestamp_op,
                                                      end_timestamp_op)
        if ts_range:
            query['timestamp'] = ts_range

        sort_keys = base._handle_sort_key('resource')
        sort_instructions = self._build_sort_instructions(sort_keys)[0]

        # use a unique collection name for the results collection,
        # as result post-sorting (as oppposed to reduce pre-sorting)
        # is not possible on an inline M-R
        out = 'resource_list_%s' % uuid.uuid4()
        self.db.meter.map_reduce(self.MAP_RESOURCES,
                                 self.REDUCE_RESOURCES,
                                 out=out,
                                 sort={'resource_id': 1},
                                 query=query)

        try:
            for r in self.db[out].find(sort=sort_instructions):
                resource = r['value']
                yield models.Resource(
                    resource_id=r['_id'],
                    user_id=resource['user_id'],
                    project_id=resource['project_id'],
                    first_sample_timestamp=resource['first_timestamp'],
                    last_sample_timestamp=resource['last_timestamp'],
                    source=resource['source'],
                    metadata=resource['metadata'])
        finally:
            self.db[out].drop()

    def _get_floating_resources(self, query, metaquery, resource):
        """Return an iterable of models.Resource instances

        Items are unconstrained by timestamp.
        :param query: project/user/source query
        :param metaquery: dict with metadata to match on.
        :param resource: resource filter.
        """
        if resource is not None:
            query['_id'] = resource

        query.update(dict((k, v)
                          for (k, v) in six.iteritems(metaquery)))

        keys = base._handle_sort_key('resource')
        sort_keys = ['last_sample_timestamp' if i == 'timestamp' else i
                     for i in keys]
        sort_instructions = self._build_sort_instructions(sort_keys)[0]

        for r in self.db.resource.find(query, sort=sort_instructions):
            yield models.Resource(
                resource_id=r['_id'],
                user_id=r['user_id'],
                project_id=r['project_id'],
                first_sample_timestamp=r.get('first_sample_timestamp',
                                             self._GENESIS),
                last_sample_timestamp=r.get('last_sample_timestamp',
                                            self._APOCALYPSE),
                source=r['source'],
                metadata=r['metadata'])

    def get_resources(self, user=None, project=None, source=None,
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None,
                      metaquery=None, resource=None, pagination=None):
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
            raise NotImplementedError('Pagination not implemented')

        metaquery = metaquery or {}

        query = {}
        if user is not None:
            query['user_id'] = user
        if project is not None:
            query['project_id'] = project
        if source is not None:
            query['source'] = source

        if start_timestamp or end_timestamp:
            return self._get_time_constrained_resources(query,
                                                        start_timestamp,
                                                        start_timestamp_op,
                                                        end_timestamp,
                                                        end_timestamp_op,
                                                        metaquery, resource)
        else:
            return self._get_floating_resources(query, metaquery, resource)

    def _aggregate_param(self, fragment_key, aggregate):
        fragment_map = self.STANDARD_AGGREGATES[fragment_key]

        if not aggregate:
            return ''.join([f for f in fragment_map.values()])

        fragments = ''

        for a in aggregate:
            if a.func in self.STANDARD_AGGREGATES[fragment_key]:
                fragment_map = self.STANDARD_AGGREGATES[fragment_key]
                fragments += fragment_map[a.func]
            elif a.func in self.UNPARAMETERIZED_AGGREGATES[fragment_key]:
                fragment_map = self.UNPARAMETERIZED_AGGREGATES[fragment_key]
                fragments += fragment_map[a.func]
            elif a.func in self.PARAMETERIZED_AGGREGATES[fragment_key]:
                fragment_map = self.PARAMETERIZED_AGGREGATES[fragment_key]
                v = self.PARAMETERIZED_AGGREGATES['validate'].get(a.func)
                if not (v and v(a.param)):
                    raise storage.StorageBadAggregate('Bad aggregate: %s.%s'
                                                      % (a.func, a.param))
                params = dict(aggregate_param=a.param)
                fragments += (fragment_map[a.func] % params)
            else:
                raise NotImplementedError('Selectable aggregate function %s'
                                          ' is not supported' % a.func)

        return fragments

    def get_meter_statistics(self, sample_filter, period=None, groupby=None,
                             aggregate=None):
        """Return an iterable of models.Statistics instance.

        Items are containing meter statistics described by the query
        parameters. The filter must have a meter value set.
        """
        if (groupby and
                set(groupby) - set(['user_id', 'project_id',
                                    'resource_id', 'source'])):
            raise NotImplementedError("Unable to group by these fields")

        q = pymongo_utils.make_query_from_filter(sample_filter)

        if period:
            if sample_filter.start:
                period_start = sample_filter.start
            else:
                period_start = self.db.meter.find(
                    limit=1, sort=[('timestamp',
                                    pymongo.ASCENDING)])[0]['timestamp']
            period_start = int(calendar.timegm(period_start.utctimetuple()))
            map_params = {'period': period,
                          'period_first': period_start,
                          'groupby_fields': json.dumps(groupby)}
            if groupby:
                map_fragment = self.MAP_STATS_PERIOD_GROUPBY
            else:
                map_fragment = self.MAP_STATS_PERIOD
        else:
            if groupby:
                map_params = {'groupby_fields': json.dumps(groupby)}
                map_fragment = self.MAP_STATS_GROUPBY
            else:
                map_params = dict()
                map_fragment = self.MAP_STATS

        sub = self._aggregate_param

        map_params['aggregate_initial_val'] = sub('emit_initial', aggregate)
        map_params['aggregate_body_val'] = sub('emit_body', aggregate)

        map_stats = map_fragment % map_params

        reduce_params = dict(
            aggregate_initial_val=sub('reduce_initial', aggregate),
            aggregate_body_val=sub('reduce_body', aggregate),
            aggregate_computation_val=sub('reduce_computation', aggregate)
        )
        reduce_stats = self.REDUCE_STATS % reduce_params

        finalize_params = dict(aggregate_val=sub('finalize', aggregate))
        finalize_stats = self.FINALIZE_STATS % finalize_params

        results = self.db.meter.map_reduce(
            map_stats,
            reduce_stats,
            {'inline': 1},
            finalize=finalize_stats,
            query=q,
        )

        # FIXME(terriyu) Fix get_meter_statistics() so we don't use sorted()
        # to return the results
        return sorted(
            (self._stats_result_to_model(r['value'], groupby, aggregate)
             for r in results['results']),
            key=operator.attrgetter('period_start'))

    @staticmethod
    def _stats_result_aggregates(result, aggregate):
        stats_args = {}
        for attr in ['count', 'min', 'max', 'sum', 'avg']:
            if attr in result:
                stats_args[attr] = result[attr]

        if aggregate:
            stats_args['aggregate'] = {}
            for a in aggregate:
                ak = '%s%s' % (a.func, '/%s' % a.param if a.param else '')
                if ak in result:
                    stats_args['aggregate'][ak] = result[ak]
                elif 'aggregate' in result:
                    stats_args['aggregate'][ak] = result['aggregate'].get(ak)
        return stats_args

    @staticmethod
    def _stats_result_to_model(result, groupby, aggregate):
        stats_args = Connection._stats_result_aggregates(result, aggregate)
        stats_args['unit'] = result['unit']
        stats_args['duration'] = result['duration']
        stats_args['duration_start'] = result['duration_start']
        stats_args['duration_end'] = result['duration_end']
        stats_args['period'] = result['period']
        stats_args['period_start'] = result['period_start']
        stats_args['period_end'] = result['period_end']
        stats_args['groupby'] = (dict(
            (g, result['groupby'][g]) for g in groupby) if groupby else None)
        return models.Statistics(**stats_args)
