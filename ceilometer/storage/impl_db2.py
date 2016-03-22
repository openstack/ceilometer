# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 eNovance
# Copyright 2013 IBM Corp
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

import bson.code
import bson.objectid
from oslo_config import cfg
from oslo_utils import timeutils
import pymongo
import six

import ceilometer
from ceilometer import storage
from ceilometer.storage import base
from ceilometer.storage import models
from ceilometer.storage.mongo import utils as pymongo_utils
from ceilometer.storage import pymongo_base
from ceilometer import utils


AVAILABLE_CAPABILITIES = {
    'resources': {'query': {'simple': True,
                            'metadata': True}},
    'statistics': {'groupby': True,
                   'query': {'simple': True,
                             'metadata': True},
                   'aggregation': {'standard': True}}
}


class Connection(pymongo_base.Connection):
    """The db2 storage for Ceilometer

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

    def __init__(self, url):

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
    def _build_sort_instructions(cls, sort_keys=None, sort_dir='desc'):
        """Returns a sort_instruction.

        Sort instructions are used in the query to determine what attributes
        to sort on and what direction to use.
        :param q: The query dict passed in.
        :param sort_keys: array of attributes by which results be sorted.
        :param sort_dir: direction in which results be sorted (asc, desc).
        :return: sort parameters
        """
        sort_keys = sort_keys or []
        sort_instructions = []
        _sort_dir = cls.SORT_OPERATION_MAP.get(
            sort_dir, cls.SORT_OPERATION_MAP['desc'])

        for _sort_key in sort_keys:
            _instruction = (_sort_key, _sort_dir)
            sort_instructions.append(_instruction)

        return sort_instructions

    def _generate_random_str(self, str_len):
        init_str = str(bson.objectid.ObjectId())
        objectid_len = len(init_str)
        if str_len >= objectid_len:
            init_str = (init_str * int(str_len/objectid_len) +
                        'x' * int(str_len % objectid_len))
        return init_str

    def upgrade(self, version=None):
        # create collection if not present
        if 'resource' not in self.db.conn.collection_names():
            self.db.conn.create_collection('resource')
        if 'meter' not in self.db.conn.collection_names():
            self.db.conn.create_collection('meter')

        # Establish indexes
        #
        # We need variations for user_id vs. project_id because of the
        # way the indexes are stored in b-trees. The user_id and
        # project_id values are usually mutually exclusive in the
        # queries, so the database won't take advantage of an index
        # including both.
        if self.db.resource.index_information() == {}:
            # Initializing a longer resource id to workaround DB2 nosql issue.
            # Longer resource id is required by compute node's resource as
            # their id is '<hostname>_<nodename>'. DB2 creates a VARCHAR(70)
            # for resource id when its length < 70. But DB2 can create a
            # VARCHAR(n) for the resource id which has n(n>70) characters.
            # Users can adjust 'db2nosql_resource_id_maxlen'(default is 512)
            # for their ENV.
            resource_id = self._generate_random_str(
                cfg.CONF.database.db2nosql_resource_id_maxlen)
            self.db.resource.insert_one({'_id': resource_id,
                                         'no_key': resource_id})
            meter_id = str(bson.objectid.ObjectId())
            timestamp = timeutils.utcnow()
            self.db.meter.insert_one({'_id': meter_id,
                                      'no_key': meter_id,
                                      'timestamp': timestamp})

            self.db.resource.create_index([
                ('user_id', pymongo.ASCENDING),
                ('project_id', pymongo.ASCENDING),
                ('source', pymongo.ASCENDING)], name='resource_idx')

            self.db.meter.create_index([
                ('resource_id', pymongo.ASCENDING),
                ('user_id', pymongo.ASCENDING),
                ('project_id', pymongo.ASCENDING),
                ('counter_name', pymongo.ASCENDING),
                ('timestamp', pymongo.ASCENDING),
                ('source', pymongo.ASCENDING)], name='meter_idx')

            self.db.meter.create_index([('timestamp',
                                         pymongo.DESCENDING)],
                                       name='timestamp_idx')

            self.db.resource.remove({'_id': resource_id})
            self.db.meter.remove({'_id': meter_id})

    def clear(self):
        # db2 does not support drop_database, remove all collections
        for col in ['resource', 'meter']:
            self.db[col].drop()
        # drop_database command does nothing on db2 database since this has
        # not been implemented. However calling this method is important for
        # removal of all the empty dbs created during the test runs since
        # test run is against mongodb on Jenkins
        self.conn.drop_database(self.db.name)
        self.conn.close()

    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.publisher.utils.meter_message_from_counter
        """
        # Record the updated resource metadata
        data = copy.deepcopy(data)
        data['resource_metadata'] = pymongo_utils.improve_keys(
            data.pop('resource_metadata'))
        self.db.resource.update_one(
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
        self.db.meter.insert_one(record)

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
                      for (k, v) in six.iteritems(metaquery)))

        if start_timestamp or end_timestamp:
            # Look for resources matching the above criteria and with
            # samples in the time range we care about, then change the
            # resource query to return just those resources by id.
            ts_range = pymongo_utils.make_timestamp_range(start_timestamp,
                                                          end_timestamp,
                                                          start_timestamp_op,
                                                          end_timestamp_op)
            if ts_range:
                q['timestamp'] = ts_range

        sort_keys = base._handle_sort_key('resource', 'timestamp')
        sort_keys.insert(0, 'resource_id')
        sort_instructions = self._build_sort_instructions(sort_keys=sort_keys,
                                                          sort_dir='desc')
        resource = lambda x: x['resource_id']
        if limit is not None:
            meters = self.db.meter.find(q, sort=sort_instructions,
                                        limit=limit)
        else:
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
                                  metadata=pymongo_utils.unquote_keys(
                latest_meter['resource_metadata']))

    def get_meter_statistics(self, sample_filter, period=None, groupby=None,
                             aggregate=None):
        """Return an iterable of models.Statistics instance.

        Items are containing meter statistics described by the query
        parameters. The filter must have a meter value set.
        """
        if (groupby and
                set(groupby) - set(['user_id', 'project_id',
                                    'resource_id', 'source'])):
            raise ceilometer.NotImplementedError(
                "Unable to group by these fields")

        if aggregate:
            raise ceilometer.NotImplementedError(
                'Selectable aggregates not implemented')

        q = pymongo_utils.make_query_from_filter(sample_filter)

        if period:
            if sample_filter.start_timestamp:
                period_start = sample_filter.start_timestamp
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
            stat = models.Statistics(unit=None,
                                     min=sys.maxsize, max=-sys.maxsize,
                                     avg=0, sum=0, count=0,
                                     period=0, period_start=0, period_end=0,
                                     duration=0, duration_start=0,
                                     duration_end=0, groupby=None)

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
                stat.period_start = (period_start +
                                     datetime.
                                     timedelta(**(_to_offset(periods))))
                stat.period_end = (period_start +
                                   datetime.
                                   timedelta(**(_to_offset(periods + 1))))
            else:
                stat.period_start = stat.duration_start
                stat.period_end = stat.duration_end
            yield stat
