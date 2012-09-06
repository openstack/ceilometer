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
"""Base classes for storage engines
"""

import abc

from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)


class StorageEngine(object):
    """Base class for storage engines.
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def register_opts(self, conf):
        """Register any configuration options used by this engine.
        """

    @abc.abstractmethod
    def get_connection(self, conf):
        """Return a Connection instance based on the configuration settings.
        """


class Connection(object):
    """Base class for storage system connections.
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __init__(self, conf):
        """Constructor"""

    @abc.abstractmethod
    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter
        """

    @abc.abstractmethod
    def get_users(self, source=None):
        """Return an iterable of user id strings.

        :param source: Optional source filter.
        """

    @abc.abstractmethod
    def get_projects(self, source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """

    @abc.abstractmethod
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

    @abc.abstractmethod
    def get_raw_events(self, event_filter):
        """Return an iterable of raw event data as created by
        :func:`ceilometer.meter.meter_message_from_counter`.
        """

    @abc.abstractmethod
    def get_volume_sum(self, event_filter):
        """Return the sum of the volume field for the events
        described by the query parameters.

        The filter must have a meter value set.

        { 'resource_id': UUID string for the resource,
          'value': The sum for the volume.
          }
        """

    @abc.abstractmethod
    def get_volume_max(self, event_filter):
        """Return the maximum of the volume field for the events
        described by the query parameters.

        The filter must have a meter value set.

        { 'resource_id': UUID string for the resource,
          'value': The max for the volume.
          }
        """

    @abc.abstractmethod
    def get_event_interval(self, event_filter):
        """Return the min and max timestamps from events,
        using the event_filter to limit the events seen.

        ( datetime.datetime(), datetime.datetime() )
        """
