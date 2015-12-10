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
"""InfluxDB meters storage backend"""

import copy
import datetime
import uuid

import influxdb
import influxdb.exceptions

from oslo_config import cfg
from oslo_log import log
from oslo_utils import timeutils
import oslo_utils
import six.moves.urllib.parse as urlparse

from ceilometer import storage
from ceilometer.storage import base
from ceilometer.storage import models
from ceilometer import utils
from ceilometer.lma.influx import utils as influx_utils

MEASUREMENT = "ceilometer"

LOG = log.getLogger(__name__)


class Connection(base.Connection):
    """Put the meters into a InlfuxDB database.

    - measurement: ceilometer
    - tags: metadata and indexed fields
    - fields: type, unit, volume
    """

    def __init__(self, url):
        super(Connection, self).__init__(url)

        user = None
        pwd = None
        host = None
        port = None

        parts = urlparse.urlparse(url)
        user_def, host_def = urlparse.splituser(parts.netloc)

        if user_def:
            auth = user_def.split(":", 1)
            if len(auth) != 2:
                raise ValueError()
            user = user_def[0]
            pwd = user_def[1]
        if host_def:
            loc = host_def.split(":", 1)
            host = loc[0]
            if len(loc) == 2:
                try:
                    port = int(loc[1])
                except ValueError:
                    raise ValueError("Port have a invalid definition.")
        if not parts.path:
            raise ValueError("Database should be defined")

        self.database = parts.path[1:]
        self.conn = influxdb.InfluxDBClient(host, port, user, pwd,
                                            self.database)

        self.upgrade()

    def upgrade(self):
        try:
            self.conn.create_database(self.database)
        except influxdb.exceptions.InfluxDBClientError as e:
            if not "database already exists" in e.content:
                raise

    def get_meter_statistics(self,
                             sample_filter,
                             period=None,
                             groupby=None,
                             aggregate=None):
        if not sample_filter.start_timestamp:
            start_timestamp = self.get_oldest_timestamp(sample_filter)
            sample_filter.start_timestamp = start_timestamp

        query = influx_utils.combine_aggregate_query(sample_filter, period,
                                                     groupby, aggregate)
        response = self.make_query(query)
        for serie, points in response.items():
            measurement, tags = serie
            for point in points:
                yield influx_utils.point_to_stat(point, tags, period,
                                                 aggregate)

    def get_oldest_timestamp(self, sample_filter):
        response = self.make_query(
            influx_utils.combine_time_bounds_query(sample_filter))
        first_point = response.get_points(MEASUREMENT).next()
        start_timestamp = utils.sanitize_timestamp(first_point['first'])
        return start_timestamp

    def make_query(self, query):
        try:
            print query
            return self.conn.query(query)
        except influxdb.InfluxDBClient as e:
            return

    def get_samples(self, sample_filter, limit=None):
        if limit is 0:
            return
        response = self.make_query(
            influx_utils.combine_list_query(sample_filter, limit))
        for point in response.get_points("ceilometer"):
            yield influx_utils.point_to_sample(point)


