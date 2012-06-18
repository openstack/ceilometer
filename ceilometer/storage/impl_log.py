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
"""Simple logging storage backend.
"""

from ceilometer import log
from ceilometer.storage import base

LOG = log.getLogger(__name__)


class LogStorage(base.StorageEngine):
    """Log the data
    """

    def register_opts(self, conf):
        """Register any configuration options used by this engine.
        """

    def get_connection(self, conf):
        """Return a Connection instance based on the configuration settings.
        """
        return Connection(conf)


class Connection(base.Connection):
    """Base class for storage system connections.
    """

    def __init__(self, conf):
        return

    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter
        """
        LOG.info('metering data %s for %s: %s',
                 data['counter_name'],
                 data['resource_id'],
                 data['counter_volume'])

    def get_users(self, source=None):
        """Return an iterable of user id strings.

        :param source: Optional source filter.
        """

    def get_resources_by_user(self, user=None, source=None):
        """Return an iterable of tuples containing resource ids and
        the most recent version of the metadata for the resource.

        :param user: The event owner.
        :param source: Optional source filter.
        """

    def get_raw_events_by_user(self, user, start=None, end=None,
                               resource=None, meter=None, source=None):
        """Return an iterable of event data.

        :param user: The event owner.
        :param start: Earliest timestamp to include.
        :param end: Only include events with timestamp less than this.
        :param resource: Optional filter for resource id.
        :param meter: Optional filter for meter type using the meter name.
        :param source: Optional source filter.
        """

    def get_volume_sum_by_user(self, user, meter, start=None, end=None,
                               resource=None, source=None):
        """Return the sum of the volume field for the events
        described by the query parameters.

        :param user: The event owner.
        :param meter: Filter for meter type using the meter name.
        :param start: Earliest timestamp to include.
        :param end: Only include events with timestamp less than this.
        :param resource: Optional filter for resource id.
        :param source: Optional source filter.
        """

    def get_duration_sum_by_user(self, user, meter, start=None, end=None,
                                 resource=None, source=None):
        """Return the sum of time for the events described by the
        query parameters.

        :param user: The event owner.
        :param meter: Filter for meter type using the meter name.
        :param start: Earliest timestamp to include.
        :param end: Only include events with timestamp less than this.
        :param resource: Optional filter for resource id.
        :param source: Optional source filter.
        """

    def get_projects(self, source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """

    def get_resources_by_project(self, project=None, source=None):
        """Return an iterable of tuples containing resource ids and
        the most recent version of the metadata for the resource.

        :param project: The event owner.
        :param source: Optional source filter.
        """

    def get_raw_events_by_project(self, project, start=None, end=None,
                               resource=None, meter=None, source=None):
        """Return an iterable of event data.

        :param project: The event owner.
        :param start: Earliest timestamp to include.
        :param end: Only include events with timestamp less than this.
        :param resource: Optional filter for resource id.
        :param meter: Optional filter for meter type using the meter name.
        :param source: Optional source filter.
        """

    def get_volume_sum_by_project(self, project, meter, start=None, end=None,
                               resource=None, source=None):
        """Return the sum of the volume field for the events
        described by the query parameters.

        :param project: The event owner.
        :param meter: Optional filter for meter type using the meter name.
        :param start: Earliest timestamp to include.
        :param end: Only include events with timestamp less than this.
        :param resource: Optional filter for resource id.
        :param source: Optional source filter.
        """

    def get_duration_sum_by_project(self, project, meter, start=None, end=None,
                                 resource=None, source=None):
        """Return the sum of time for the events described by the
        query parameters.

        :param project: The event owner.
        :param meter: Optional filter for meter type using the meter name.
        :param start: Earliest timestamp to include.
        :param end: Only include events with timestamp less than this.
        :param resource: Optional filter for resource id.
        :param source: Optional source filter.
        """
