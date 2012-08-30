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

import copy
import datetime

from ceilometer.openstack.common import log
from ceilometer.openstack.common import cfg
from ceilometer.storage import base

import bson.code
import pymongo
import re

from urlparse import urlparse

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

    OPTIONS = []

    def register_opts(self, conf):
        """Register any configuration options used by this engine.
        """
        conf.register_opts(self.OPTIONS)

    def get_connection(self, conf):
        """Return a Connection instance based on the configuration settings.
        """
        return Connection(conf)


def make_timestamp_range(start, end):
    """Given two possible datetimes, create the query
    document to find timestamps within that range
    using $gte for the lower bound and $lt for the
    upper bound.
    """
    ts_range = {}
    if start:
        ts_range['$gte'] = start
    if end:
        ts_range['$lt'] = end
    return ts_range


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

    if event_filter.meter:
        q['counter_name'] = event_filter.meter
    elif require_meter:
        raise RuntimeError('Missing required meter specifier')

    ts_range = make_timestamp_range(event_filter.start, event_filter.end)
    if ts_range:
        q['timestamp'] = ts_range

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
        opts = self._parse_connection_url(conf.database_connection)
        LOG.info('connecting to MongoDB on %s:%s', opts['host'], opts['port'])
        self.conn = self._get_connection(opts)
        self.db = getattr(self.conn, opts['dbname'])
        if 'username' in opts:
            self.db.authenticate(opts['username'], opts['password'])

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
                    ])
            self.db.meter.ensure_index([
                    ('resource_id', pymongo.ASCENDING),
                    (primary, pymongo.ASCENDING),
                    ('counter_name', pymongo.ASCENDING),
                    ('timestamp', pymongo.ASCENDING),
                    ('source', pymongo.ASCENDING),
                    ])
        return

    def _get_connection(self, opts):
        """Return a connection to the database.

        .. note::

          The tests use a subclass to override this and return an
          in-memory connection.
        """
        return pymongo.Connection(opts['host'], opts['port'], safe=True)

    def _parse_connection_url(self, url):
        opts = {}
        result = urlparse(url)
        opts['dbtype'] = result.scheme
        opts['dbname'] = result.path.replace('/', '')
        netloc_match = re.match(r'(?:(\w+:\w+)@)?(.*)', result.netloc)
        auth = netloc_match.group(1)
        netloc = netloc_match.group(2)
        if auth:
            opts['username'], opts['password'] = auth.split(':')
        if ':' in netloc:
            opts['host'], port = netloc.split(':')
        else:
            opts['host'] = netloc
            port = 27017
        opts['port'] = port and int(port) or 27017
        return opts

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
        received_timestamp = datetime.datetime.utcnow()
        self.db.resource.update(
            {'_id': data['resource_id']},
            {'$set': {'project_id': data['project_id'],
                      'user_id': data['user_id'],
                      # Current metadata being used and when it was
                      # last updated.
                      'timestamp': data['timestamp'],
                      'received_timestamp': received_timestamp,
                      'metadata': data['resource_metadata'],
                      'source': data['source'],
                      },
             '$addToSet': {'meter': {'counter_name': data['counter_name'],
                                     'counter_type': data['counter_type'],
                                     },
                           },
             },
            upsert=True,
            )

        # Record the raw data for the event. Use a copy so we do not
        # modify a data structure owned by our caller (the driver adds
        # a new key '_id').
        record = copy.copy(data)
        self.db.meter.insert(record)
        return

    def get_users(self, source=None):
        """Return an iterable of user id strings.

        :param source: Optional source filter.
        """
        q = {}
        if source is not None:
            q['source'] = source
        return sorted(self.db.user.find(q).distinct('_id'))

    def get_projects(self, source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """
        q = {}
        if source is not None:
            q['source'] = source
        return sorted(self.db.project.find(q).distinct('_id'))

    def get_resources(self, user=None, project=None, source=None,
                      start_timestamp=None, end_timestamp=None):
        """Return an iterable of dictionaries containing resource information.

        { 'resource_id': UUID of the resource,
          'project_id': UUID of project owning the resource,
          'user_id': UUID of user owning the resource,
          'timestamp': UTC datetime of last update to the resource,
          'metadata': most current metadata for the resource,
          'meter': list of the meters reporting data for the resource,
          }

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param source: Optional source filter.
        :param start_timestamp: Optional modified timestamp start range.
        :param end_timestamp: Optional modified timestamp end range.
        """
        q = {}
        if user is not None:
            q['user_id'] = user
        if project is not None:
            q['project_id'] = project
        if source is not None:
            q['source'] = source
        # FIXME(dhellmann): This may not perform very well,
        # but doing any better will require changing the database
        # schema and that will need more thought than I have time
        # to put into it today.
        if start_timestamp or end_timestamp:
            # Look for resources matching the above criteria and with
            # events in the time range we care about, then change the
            # resource query to return just those resources by id.
            ts_range = make_timestamp_range(start_timestamp, end_timestamp)
            if ts_range:
                q['timestamp'] = ts_range
            resource_ids = self.db.meter.find(q).distinct('resource_id')
            # Overwrite the query to just filter on the ids
            # we have discovered to be interesting.
            q = {'_id': {'$in': resource_ids}}
        for resource in self.db.resource.find(q):
            r = {}
            r.update(resource)
            # Replace the '_id' key with 'resource_id' to meet the
            # caller's expectations.
            r['resource_id'] = r['_id']
            del r['_id']
            yield r

    def get_raw_events(self, event_filter):
        """Return an iterable of raw event data as created by
        :func:`ceilometer.meter.meter_message_from_counter`.
        """
        q = make_query_from_filter(event_filter, require_meter=False)
        events = self.db.meter.find(q)
        for e in events:
            # Remove the ObjectId generated by the database when
            # the event was inserted. It is an implementation
            # detail that should not leak outside of the driver.
            del e['_id']
            yield e

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
