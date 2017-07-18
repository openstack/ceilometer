#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 eNovance
# Copyright 2014 Red Hat, Inc
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

import itertools
import operator

import copy
import datetime
import uuid

import bson.code
import bson.objectid
from oslo_log import log
from oslo_utils import timeutils
import pymongo
import six

import ceilometer
from ceilometer.i18n import _
from ceilometer import storage
from ceilometer.storage import base
from ceilometer.storage import models
from ceilometer.storage.mongo import utils as pymongo_utils
from ceilometer.storage import pymongo_base
from ceilometer import utils

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

    STANDARD_AGGREGATES = dict([(a.name, a) for a in [
        pymongo_utils.SUM_AGGREGATION, pymongo_utils.AVG_AGGREGATION,
        pymongo_utils.MIN_AGGREGATION, pymongo_utils.MAX_AGGREGATION,
        pymongo_utils.COUNT_AGGREGATION,
    ]])

    AGGREGATES = dict([(a.name, a) for a in [
        pymongo_utils.SUM_AGGREGATION,
        pymongo_utils.AVG_AGGREGATION,
        pymongo_utils.MIN_AGGREGATION,
        pymongo_utils.MAX_AGGREGATION,
        pymongo_utils.COUNT_AGGREGATION,
        pymongo_utils.STDDEV_AGGREGATION,
        pymongo_utils.CARDINALITY_AGGREGATION,
    ]])

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

    def __init__(self, conf, url):
        super(Connection, self).__init__(conf, url)

        # NOTE(jd) Use our own connection pooling on top of the Pymongo one.
        # We need that otherwise we overflow the MongoDB instance with new
        # connection since we instantiate a Pymongo client each time someone
        # requires a new storage connection.
        self.conn = self.CONNECTION_POOL.connect(conf, url)
        self.version = self.conn.server_info()['versionArray']
        # Require MongoDB 2.4 to use $setOnInsert
        if self.version < pymongo_utils.MINIMUM_COMPATIBLE_MONGODB_VERSION:
            raise storage.StorageBadVersion(
                "Need at least MongoDB %s" %
                pymongo_utils.MINIMUM_COMPATIBLE_MONGODB_VERSION)

        connection_options = pymongo.uri_parser.parse_uri(url)
        self.db = getattr(self.conn, connection_options['database'])
        if connection_options.get('username'):
            self.db.authenticate(connection_options['username'],
                                 connection_options['password'])

        # NOTE(jd) Upgrading is just about creating index, so let's do this
        # on connection to be sure at least the TTL is correctly updated if
        # needed.
        self.upgrade()

    @staticmethod
    def update_ttl(ttl, ttl_index_name, index_field, coll):
        """Update or create time_to_live indexes.

        :param ttl: time to live in seconds.
        :param ttl_index_name: name of the index we want to update or create.
        :param index_field: field with the index that we need to update.
        :param coll: collection which indexes need to be updated.
        """
        indexes = coll.index_information()
        if ttl <= 0:
            if ttl_index_name in indexes:
                coll.drop_index(ttl_index_name)
            return

        if ttl_index_name in indexes:
            return coll.database.command(
                'collMod', coll.name,
                index={'keyPattern': {index_field: pymongo.ASCENDING},
                       'expireAfterSeconds': ttl})

        coll.create_index([(index_field, pymongo.ASCENDING)],
                          expireAfterSeconds=ttl,
                          name=ttl_index_name)

    def upgrade(self):
        # Establish indexes
        #
        # We need variations for user_id vs. project_id because of the
        # way the indexes are stored in b-trees. The user_id and
        # project_id values are usually mutually exclusive in the
        # queries, so the database won't take advantage of an index
        # including both.

        # create collection if not present
        if 'resource' not in self.db.conn.collection_names():
            self.db.conn.create_collection('resource')
        if 'meter' not in self.db.conn.collection_names():
            self.db.conn.create_collection('meter')

        name_qualifier = dict(user_id='', project_id='project_')
        background = dict(user_id=False, project_id=True)
        for primary in ['user_id', 'project_id']:
            name = 'meter_%sidx' % name_qualifier[primary]
            self.db.meter.create_index([
                ('resource_id', pymongo.ASCENDING),
                (primary, pymongo.ASCENDING),
                ('counter_name', pymongo.ASCENDING),
                ('timestamp', pymongo.ASCENDING),
            ], name=name, background=background[primary])

        self.db.meter.create_index([('timestamp', pymongo.DESCENDING)],
                                   name='timestamp_idx')

        # NOTE(ityaptin) This index covers get_resource requests sorting
        # and MongoDB uses part of this compound index for different
        # queries based on any of user_id, project_id, last_sample_timestamp
        # fields
        self.db.resource.create_index([('user_id', pymongo.DESCENDING),
                                       ('project_id', pymongo.DESCENDING),
                                       ('last_sample_timestamp',
                                        pymongo.DESCENDING)],
                                      name='resource_user_project_timestamp',)
        self.db.resource.create_index([('last_sample_timestamp',
                                        pymongo.DESCENDING)],
                                      name='last_sample_timestamp_idx')

        # update or create time_to_live index
        ttl = self.conf.database.metering_time_to_live
        self.update_ttl(ttl, 'meter_ttl', 'timestamp', self.db.meter)
        self.update_ttl(ttl, 'resource_ttl', 'last_sample_timestamp',
                        self.db.resource)

    def clear(self):
        self.conn.drop_database(self.db.name)
        # Connection will be reopened automatically if needed
        self.conn.close()

    def record_metering_data(self, data):
        # TODO(liusheng): this is a workaround that is because there are
        # storage scenario tests which directly invoke this method and pass a
        # sample dict with all the storage backends and
        # call conn.record_metering_data. May all the Ceilometer
        # native storage backends can support batch recording in future, and
        # then we need to refactor the scenario tests.
        self.record_metering_data_batch([data])

    def record_metering_data_batch(self, samples):
        """Record the metering data in batch.

        :param samples: a list of samples dict.
        """
        # Record the updated resource metadata - we use $setOnInsert to
        # unconditionally insert sample timestamps and resource metadata
        # (in the update case, this must be conditional on the sample not
        # being out-of-order)

        # We must not store this
        samples = copy.deepcopy(samples)

        for sample in samples:
            sample.pop("monotonic_time", None)

        sorted_samples = sorted(
            copy.deepcopy(samples),
            key=lambda s: (s['resource_id'], s['timestamp']))
        res_grouped_samples = itertools.groupby(
            sorted_samples, key=operator.itemgetter('resource_id'))
        samples_to_update_resource = []
        for resource_id, g_samples in res_grouped_samples:
            g_samples = list(g_samples)
            g_samples[-1]['meter'] = [{'counter_name': s['counter_name'],
                                       'counter_type': s['counter_type'],
                                       'counter_unit': s['counter_unit'],
                                       } for s in g_samples]
            g_samples[-1]['last_sample_timestamp'] = g_samples[-1]['timestamp']
            g_samples[-1]['first_sample_timestamp'] = g_samples[0]['timestamp']
            samples_to_update_resource.append(g_samples[-1])
        for sample in samples_to_update_resource:
            sample['resource_metadata'] = pymongo_utils.improve_keys(
                sample.pop('resource_metadata'))
            resource = self.db.resource.find_one_and_update(
                {'_id': sample['resource_id']},
                {'$set': {'project_id': sample['project_id'],
                          'user_id': sample['user_id'],
                          'source': sample['source'],
                          },
                 '$setOnInsert': {
                     'metadata': sample['resource_metadata'],
                     'first_sample_timestamp': sample['timestamp'],
                     'last_sample_timestamp': sample['timestamp'],
                    },
                 '$addToSet': {
                     'meter': {'$each': sample['meter']},
                    },
                 },
                upsert=True,
                return_document=pymongo.ReturnDocument.AFTER,
            )

            # only update last sample timestamp if actually later (the usual
            # in-order case)
            last_sample_timestamp = resource.get('last_sample_timestamp')
            if (last_sample_timestamp is None or
                    last_sample_timestamp <= sample['last_sample_timestamp']):
                self.db.resource.update_one(
                    {'_id': sample['resource_id']},
                    {'$set': {'metadata': sample['resource_metadata'],
                              'last_sample_timestamp':
                                  sample['last_sample_timestamp']}}
                )

            # only update first sample timestamp if actually earlier (
            # the unusual out-of-order case)
            # NOTE: a null first sample timestamp is not updated as this
            # indicates a pre-existing resource document dating from before
            # we started recording these timestamps in the resource collection
            first_sample_timestamp = resource.get('first_sample_timestamp')
            if (first_sample_timestamp is not None and
                    first_sample_timestamp > sample['first_sample_timestamp']):
                self.db.resource.update_one(
                    {'_id': sample['resource_id']},
                    {'$set': {'first_sample_timestamp':
                              sample['first_sample_timestamp']}}
                )

        # Record the raw data for the meter. Use a copy so we do not
        # modify a data structure owned by our caller (the driver adds
        # a new key '_id').
        record = copy.deepcopy(samples)
        for s in record:
            s['recorded_at'] = timeutils.utcnow()
            s['resource_metadata'] = pymongo_utils.improve_keys(
                s.pop('resource_metadata'))
        self.db.meter.insert_many(record)

    def clear_expired_metering_data(self, ttl):
        """Clear expired data from the backend storage system.

        Clearing occurs with native MongoDB time-to-live feature.
        """
        LOG.debug("Clearing expired metering data is based on native "
                  "MongoDB time to live feature and going in background.")

    @classmethod
    def _build_sort_instructions(cls, sort_keys=None, sort_dir='desc'):
        """Returns a sort_instruction and paging operator.

        Sort instructions are used in the query to determine what attributes
        to sort on and what direction to use.
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

    def _get_time_constrained_resources(self, query,
                                        start_timestamp, start_timestamp_op,
                                        end_timestamp, end_timestamp_op,
                                        metaquery, resource, limit):
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
            if limit is not None:
                results = self.db[out].find(sort=sort_instructions,
                                            limit=limit)
            else:
                results = self.db[out].find(sort=sort_instructions)
            for r in results:
                resource = r['value']
                yield models.Resource(
                    resource_id=r['_id'],
                    user_id=resource['user_id'],
                    project_id=resource['project_id'],
                    first_sample_timestamp=resource['first_timestamp'],
                    last_sample_timestamp=resource['last_timestamp'],
                    source=resource['source'],
                    metadata=pymongo_utils.unquote_keys(resource['metadata']))
        finally:
            self.db[out].drop()

    def _get_floating_resources(self, query, metaquery, resource, limit):
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

        if limit is not None:
            results = self.db.resource.find(query, sort=sort_instructions,
                                            limit=limit)
        else:
            results = self.db.resource.find(query, sort=sort_instructions)

        for r in results:
            yield models.Resource(
                resource_id=r['_id'],
                user_id=r['user_id'],
                project_id=r['project_id'],
                first_sample_timestamp=r.get('first_sample_timestamp',
                                             self._GENESIS),
                last_sample_timestamp=r.get('last_sample_timestamp',
                                            self._APOCALYPSE),
                source=r['source'],
                metadata=pymongo_utils.unquote_keys(r['metadata']))

    def get_resources(self, user=None, project=None, source=None,
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None,
                      metaquery=None, resource=None, limit=None):
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
        :param limit: Maximum number of results to return.
        """
        if limit == 0:
            return
        metaquery = pymongo_utils.improve_keys(metaquery, metaquery=True) or {}

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
                                                        metaquery, resource,
                                                        limit)
        else:
            return self._get_floating_resources(query, metaquery, resource,
                                                limit)

    @staticmethod
    def _make_period_dict(period, first_ts):
        """Create a period field for _id of grouped fields.

        :param period: Period duration in seconds
        :param first_ts: First timestamp for first period
        :return:
        """
        if period >= 0:
            period_unique_dict = {
                "period_start":
                    {
                        "$divide": [
                            {"$subtract": [
                                {"$subtract": ["$timestamp",
                                               first_ts]},
                                {"$mod": [{"$subtract": ["$timestamp",
                                                         first_ts]},
                                          period * 1000]
                                 }
                            ]},
                            period * 1000
                        ]
                    }

            }
        else:
            # Note(ityaptin) Hack for older MongoDB versions (2.4.+ and older).
            # Since 2.6+ we could use $literal operator
            period_unique_dict = {"$period_start": {"$add": [0, 0]}}
        return period_unique_dict

    def get_meter_statistics(self, sample_filter, period=None, groupby=None,
                             aggregate=None):
        """Return an iterable of models.Statistics instance.

        Items are containing meter statistics described by the query
        parameters. The filter must have a meter value set.
        """
        # NOTE(zqfan): We already have checked at API level, but
        # still leave it here in case of directly storage calls.
        if aggregate:
            for a in aggregate:
                if a.func not in self.AGGREGATES:
                    msg = _('Invalid aggregation function: %s') % a.func
                    raise storage.StorageBadAggregate(msg)

        if (groupby and set(groupby) -
            set(['user_id', 'project_id', 'resource_id', 'source',
                 'resource_metadata.instance_type'])):
            raise ceilometer.NotImplementedError(
                "Unable to group by these fields")
        q = pymongo_utils.make_query_from_filter(sample_filter)

        group_stage = {}
        project_stage = {
            "unit": "$_id.unit",
            "name": "$_id.name",
            "first_timestamp": "$first_timestamp",
            "last_timestamp": "$last_timestamp",
            "period_start": "$_id.period_start",
        }

        # Add timestamps to $group stage
        group_stage.update({"first_timestamp": {"$min": "$timestamp"},
                            "last_timestamp": {"$max": "$timestamp"}})

        # Define a _id field for grouped documents
        unique_group_field = {"name": "$counter_name",
                              "unit": "$counter_unit"}

        # Define a first timestamp for periods
        if sample_filter.start_timestamp:
            first_timestamp = sample_filter.start_timestamp
        else:
            first_timestamp_cursor = self.db.meter.find(
                limit=1, sort=[('timestamp',
                                pymongo.ASCENDING)])
            if first_timestamp_cursor.count():
                first_timestamp = first_timestamp_cursor[0]['timestamp']
            else:
                first_timestamp = utils.EPOCH_TIME

        # Add a start_period field to unique identifier of grouped documents
        if period:
            period_dict = self._make_period_dict(period,
                                                 first_timestamp)
            unique_group_field.update(period_dict)

        # Add a groupby fields to unique identifier of grouped documents
        if groupby:
            unique_group_field.update(dict((field.replace(".", "/"),
                                            "$%s" % field)
                                      for field in groupby))

        group_stage.update({"_id": unique_group_field})

        self._compile_aggregate_stages(aggregate, group_stage, project_stage)

        # Aggregation stages list. It's work one by one and uses documents
        # from previous stages.
        aggregation_query = [{'$match': q},
                             {"$sort": {"timestamp": 1}},
                             {"$group": group_stage},
                             {"$sort": {"_id.period_start": 1}},
                             {"$project": project_stage}]

        # results is dict in pymongo<=2.6.3 and CommandCursor in >=3.0
        results = self.db.meter.aggregate(aggregation_query,
                                          **self._make_aggregation_params())
        return [self._stats_result_to_model(point, groupby, aggregate,
                                            period, first_timestamp)
                for point in self._get_results(results)]

    def _stats_result_aggregates(self, result, aggregate):
        stats_args = {}
        for attr, func in Connection.STANDARD_AGGREGATES.items():
            if attr in result:
                stats_args.update(func.finalize(result,
                                                version_array=self.version))

        if aggregate:
            stats_args['aggregate'] = {}
            for agr in aggregate:
                stats_args['aggregate'].update(
                    Connection.AGGREGATES[agr.func].finalize(
                        result, agr.param, self.version))
        return stats_args

    def _stats_result_to_model(self, result, groupby, aggregate, period,
                               first_timestamp):
        if period is None:
            period = 0
        first_timestamp = pymongo_utils.from_unix_timestamp(first_timestamp)
        stats_args = self._stats_result_aggregates(result, aggregate)

        stats_args['unit'] = result['unit']
        stats_args['duration'] = (result["last_timestamp"] -
                                  result["first_timestamp"]).total_seconds()
        stats_args['duration_start'] = result['first_timestamp']
        stats_args['duration_end'] = result['last_timestamp']
        stats_args['period'] = period
        start = result.get("period_start", 0) * period

        stats_args['period_start'] = (first_timestamp +
                                      datetime.timedelta(seconds=start))
        stats_args['period_end'] = (first_timestamp +
                                    datetime.timedelta(seconds=start + period)
                                    if period else result['last_timestamp'])

        stats_args['groupby'] = (
            dict((g, result['_id'].get(g.replace(".", "/")))
                 for g in groupby) if groupby else None)
        return models.Statistics(**stats_args)

    def _compile_aggregate_stages(self, aggregate, group_stage, project_stage):
        if not aggregate:
            for aggregation in Connection.STANDARD_AGGREGATES.values():
                group_stage.update(
                    aggregation.group(version_array=self.version)
                )
                project_stage.update(
                    aggregation.project(
                        version_array=self.version
                    )
                )
        else:
            for description in aggregate:
                aggregation = Connection.AGGREGATES.get(description.func)
                if aggregation:
                    if not aggregation.validate(description.param):
                        raise storage.StorageBadAggregate(
                            'Bad aggregate: %s.%s' % (description.func,
                                                      description.param))
                    group_stage.update(
                        aggregation.group(description.param,
                                          version_array=self.version)
                    )
                    project_stage.update(
                        aggregation.project(description.param,
                                            version_array=self.version)
                    )

    @staticmethod
    def _get_results(results):
        if isinstance(results, dict):
            return results.get('result', [])
        else:
            return results

    def _make_aggregation_params(self):
        if self.version >= pymongo_utils.COMPLETE_AGGREGATE_COMPATIBLE_VERSION:
            return {"allowDiskUse": True}
        return {}
