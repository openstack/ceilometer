# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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

import datetime

from ceilometer import log
from ceilometer.openstack.common import cfg
from ceilometer.storage import base

import bson.code
import pymongo

LOG = log.getLogger(__name__)


class MongoDBStorage(base.StorageEngine):
    """Put the data into a MongoDB database

    Collections:

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
          timestamp: datetime of last update
          user_id: uuid
          project_id: uuid
          meter: [ array of {counter_name: string, counter_type: string} ]
        }
    """

    OPTIONS = [
        cfg.StrOpt('mongodb_dbname',
                   default='ceilometer',
                   help='Database name',
                   ),
        cfg.StrOpt('mongodb_host',
                   default='localhost',
                   help='hostname or IP of server running MongoDB',
                   ),
        cfg.IntOpt('mongodb_port',
                   default=27017,
                   help='port number where MongoDB is running',
                   ),
        ]

    def register_opts(self, conf):
        """Register any configuration options used by this engine.
        """
        conf.register_opts(self.OPTIONS)

    def get_connection(self, conf):
        """Return a Connection instance based on the configuration settings.
        """
        return Connection(conf)


def make_query_from_filter(event_filter, require_meter=True):
    """Return a query dictionary based on the settings in the filter.

    :param filter: EventFilter instance
    :param require_meter: If true and the filter does not have a meter,
                          raise an error.
    """
    q = {}

    if event_filter.user:
        q['user_id'] = event_filter.user
    elif event_filter.project:
        q['project_id'] = event_filter.project
    else:
        # NOTE(dhellmann): The EventFilter class should have detected
        # this case already, but just in case someone passes something
        # that isn't actually an EventFilter instance...
        raise RuntimeError('One of "user" or "project" is required')

    if event_filter.meter:
        q['counter_name'] = event_filter.meter
    elif require_meter:
        raise RuntimeError('Missing required meter specifier')

    if event_filter.start:
        q['timestamp'] = {'$gte': event_filter.start}
    if event_filter.end:
        q['timestamp'] = {'$lt': event_filter.end}
    if event_filter.resource:
        q['resource_id'] = event_filter.resource
    if event_filter.source:
        q['source'] = event_filter.source

    return q


class Connection(base.Connection):
    """MongoDB connection.
    """

    # JavaScript function for doing map-reduce to get a counter volume
    # total.
    MAP_COUNTER_VOLUME = bson.code.Code("""
        function() {
            emit(this.resource_id, this.counter_volume);
        }
        """)

    # JavaScript function for doing map-reduce to get a counter
    # duration total.
    MAP_COUNTER_DURATION = bson.code.Code("""
        function() {
            emit(this.resource_id, this.counter_duration);
        }
        """)

    # JavaScript function for doing map-reduce to get a maximum value
    # from a range.  (from
    # http://cookbook.mongodb.org/patterns/finding_max_and_min/)
    REDUCE_MAX = bson.code.Code("""
        function (key, values) {
            return Math.max.apply(Math, values);
        }
        """)

    # JavaScript function for doing map-reduce to get a sum.
    REDUCE_SUM = bson.code.Code("""
        function (key, values) {
            var total = 0;
            for (var i = 0; i < values.length; i++) {
                total += values[i];
            }
            return total;
        }
        """)

    def __init__(self, conf):
        LOG.info('connecting to MongoDB on %s:%s',
                 conf.mongodb_host, conf.mongodb_port)
        self.conn = self._get_connection(conf)
        self.db = getattr(self.conn, conf.mongodb_dbname)
        return

    def _get_connection(self, conf):
        """Return a connection to the database.

        .. note::

          The tests use a subclass to override this and return an
          in-memory connection.
        """
        return pymongo.Connection(conf.mongodb_host,
                                  conf.mongodb_port,
                                  safe=True,
                                  )

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
        timestamp = datetime.datetime.utcnow()
        self.db.resource.update(
            {'_id': data['resource_id']},
            {'$set': {'project_id': data['project_id'],
                      'user_id': data['user_id'],
                      # Current metadata being used and when it was
                      # last updated.
                      'timestamp': timestamp,
                      'metadata': data['resource_metadata'],
                      },
             '$addToSet': {'meter': {'counter_name': data['counter_name'],
                                     'counter_type': data['counter_type'],
                                     },
                           },
             },
            upsert=True,
            )

        # Record the raw data for the event
        self.db.meter.insert(data)
        return

    def get_users(self, source=None):
        """Return an iterable of user id strings.

        :param source: Optional source filter.
        """
        q = {}
        if source is not None:
            q['source'] = source
        return self.db.user.distinct('_id')

    def get_projects(self, source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """
        q = {}
        if source is not None:
            q['source'] = source
        return self.db.project.distinct('_id')

    def get_resources(self, user=None, project=None, source=None):
        """Return an iterable of dictionaries containing resource information.

        { 'resource_id': UUID of the resource,
          'project_id': UUID of project owning the resource,
          'user_id': UUID of user owning the resource,
          'timestamp': UTC datetime of last update to the resource,
          'metadata': most current metadata for the resource,
          'meter': list of the meters reporting data for the resource,
          }

        :param user: Optional resource owner.
        :param project: Optional resource owner.
        :param source: Optional source filter.
        """
        q = {}
        if user is not None:
            q['user_id'] = user
        if project is not None:
            q['project_id'] = project
        if source is not None:
            q['source'] = source
        for resource in self.db.resource.find(q):
            r = {}
            r.update(resource)
            r['resource_id'] = r['_id']
            del r['_id']
            yield r

    def get_raw_events(self, event_filter):
        """Return an iterable of event data.
        """
        q = make_query_from_filter(event_filter, require_meter=False)
        events = self.db.meter.find(q)
        return events

    def get_volume_sum(self, event_filter):
        """Return the sum of the volume field for the events
        described by the query parameters.
        """
        q = make_query_from_filter(event_filter)
        results = self.db.meter.map_reduce(self.MAP_COUNTER_VOLUME,
                                           self.REDUCE_SUM,
                                           {'inline': 1},
                                           query=q,
                                           )
        return ({'resource_id': r['_id'], 'value': r['value']}
                for r in results['results'])

    def get_volume_max(self, event_filter):
        """Return the maximum of the volume field for the events
        described by the query parameters.
        """
        q = make_query_from_filter(event_filter)
        results = self.db.meter.map_reduce(self.MAP_COUNTER_VOLUME,
                                           self.REDUCE_MAX,
                                           {'inline': 1},
                                           query=q,
                                           )
        return ({'resource_id': r['_id'], 'value': r['value']}
                for r in results['results'])

    def get_duration_sum(self, event_filter):
        """Return the sum of time for the events described by the
        query parameters.
        """
        q = make_query_from_filter(event_filter)
        results = self.db.meter.map_reduce(self.MAP_COUNTER_DURATION,
                                           self.REDUCE_MAX,
                                           {'inline': 1},
                                           query=q,
                                           )
        return ({'resource_id': r['_id'], 'value': r['value']}
                for r in results['results'])
