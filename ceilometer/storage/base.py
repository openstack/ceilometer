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
import datetime
import math

from ceilometer.openstack.common import timeutils


def iter_period(start, end, period):
    """Split a time from start to end in periods of a number of seconds. This
    function yield the (start, end) time for each period composing the time
    passed as argument.

    :param start: When the period set start.
    :param end: When the period end starts.
    :param period: The duration of the period.

    """
    period_start = start
    increment = datetime.timedelta(seconds=period)
    for i in xrange(int(math.ceil(
            timeutils.delta_seconds(start, end)
            / float(period)))):
        next_start = period_start + increment
        yield (period_start, next_start)
        period_start = next_start


class StorageEngine(object):
    """Base class for storage engines."""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def register_opts(self, conf):
        """Register any configuration options used by this engine."""

    @abc.abstractmethod
    def get_connection(self, conf):
        """Return a Connection instance based on the configuration settings."""


class Connection(object):
    """Base class for storage system connections."""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __init__(self, conf):
        """Constructor."""

    @abc.abstractmethod
    def upgrade(self, version=None):
        """Migrate the database to `version` or the most recent version."""

    @abc.abstractmethod
    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter

        All timestamps must be naive utc datetime object.
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
                      start_timestamp=None, end_timestamp=None,
                      metaquery={}, resource=None):
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
        :param metaquery: Optional dict with metadata to match on.
        :param resource: Optional resource filter.
        """

    @abc.abstractmethod
    def get_meters(self, user=None, project=None, resource=None, source=None,
                   metaquery={}):
        """Return an iterable of dictionaries containing meter information.

        { 'name': name of the meter,
          'type': type of the meter (guage, counter),
          'unit': unit of the meter,
          'resource_id': UUID of the resource,
          'project_id': UUID of project owning the resource,
          'user_id': UUID of user owning the resource,
          }

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional resource filter.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        """

    @abc.abstractmethod
    def get_samples(self, event_filter):
        """Return an iterable of samples as created by
        :func:`ceilometer.meter.meter_message_from_counter`.
        """

    @abc.abstractmethod
    def get_event_interval(self, event_filter):
        """Return the min and max timestamps from samples,
        using the event_filter to limit the samples seen.

        ( datetime.datetime(), datetime.datetime() )
        """

    @abc.abstractmethod
    def get_meter_statistics(self, event_filter, period=None):
        """Return a dictionary containing meter statistics.
        described by the query parameters.

        The filter must have a meter value set.

        { 'min':
          'max':
          'avg':
          'sum':
          'count':
          'period':
          'period_start':
          'period_end':
          'duration':
          'duration_start':
          'duration_end':
          }

        """

    @abc.abstractmethod
    def clear(self):
        """Clear database."""
