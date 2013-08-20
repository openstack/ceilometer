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


def _handle_sort_key(model_name, sort_key=None):
    """Generate sort keys according to the passed in sort key from user.

    :param model_name: Database model name be query.(alarm, meter, etc.)
    :param sort_key: sort key passed from user.
    return: sort keys list
    """
    sort_keys_extra = {'alarm': ['name', 'user_id', 'project_id'],
                       'meter': ['user_id', 'project_id'],
                       'resource': ['user_id', 'project_id', 'timestamp'],
                       }

    sort_keys = sort_keys_extra[model_name]
    if not sort_key:
        return sort_keys
    # NOTE(Fengqian): We need to put the sort key from user
    #in the first place of sort keys list.
    try:
        sort_keys.remove(sort_key)
    except ValueError:
        pass
    finally:
        sort_keys.insert(0, sort_key)
    return sort_keys


class MultipleResultsFound(Exception):
    pass


class NoResultFound(Exception):
    pass


class Pagination(object):
    """Class for pagination query."""

    def __init__(self, limit=None, primary_sort_dir='desc', sort_keys=[],
                 sort_dirs=[], marker_value=None):
        """This puts all parameters used for paginate query together.

        :param limit: Maximum number of items to return;
        :param primary_sort_dir: Sort direction of primary key.
        :param marker_value: Value of primary key to identify the last item of
                             the previous page.
        :param sort_keys: Array of attributes passed in by users to sort the
                            results besides the primary key.
        :param sort_dirs: Per-column array of sort_dirs, corresponding to
                            sort_keys.
        """
        self.limit = limit
        self.primary_sort_dir = primary_sort_dir
        self.marker_value = marker_value
        self.sort_keys = sort_keys
        self.sort_dirs = sort_dirs


class StorageEngine(object):
    """Base class for storage engines."""

    __metaclass__ = abc.ABCMeta

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
    def upgrade(self):
        """Migrate the database to `version` or the most recent version."""

    @abc.abstractmethod
    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter

        All timestamps must be naive utc datetime object.
        """

    @abc.abstractmethod
    def clear_expired_metering_data(self, ttl):
        """Clear expired data from the backend storage system according to the
        time-to-live.

        :param ttl: Number of seconds to keep records for.

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
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None,
                      metaquery={}, resource=None, pagination=None):
        """Return an iterable of models.Resource instances containing
        resource information.

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param source: Optional source filter.
        :param start_timestamp: Optional modified timestamp start range.
        :param start_timestamp_op: Optional timestamp start range operation.
        :param end_timestamp: Optional modified timestamp end range.
        :param end_timestamp_op: Optional timestamp end range operation.
        :param metaquery: Optional dict with metadata to match on.
        :param resource: Optional resource filter.
        :param pagination: Optional pagination query.
        """

    @abc.abstractmethod
    def get_meters(self, user=None, project=None, resource=None, source=None,
                   metaquery={}, pagination=None):
        """Return an iterable of model.Meter instances containing meter
        information.

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional resource filter.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param pagination: Optional pagination query.
        """

    @abc.abstractmethod
    def get_samples(self, sample_filter, limit=None):
        """Return an iterable of model.Sample instances.

        :param sample_filter: Filter.
        :param limit: Maximum number of results to return.
        """

    @abc.abstractmethod
    def get_meter_statistics(self, sample_filter, period=None, groupby=None):
        """Return an iterable of model.Statistics instances.

        The filter must have a meter value set.
        """

    @abc.abstractmethod
    def get_alarms(self, name=None, user=None,
                   project=None, enabled=True, alarm_id=None, pagination=None):
        """Yields a lists of alarms that match filters
        """

    @abc.abstractmethod
    def create_alarm(self, alarm):
        """Create an alarm. Returns the alarm as created.

        :param alarm: The alarm to create.
        """

    @abc.abstractmethod
    def update_alarm(self, alarm):
        """update alarm
        """

    @abc.abstractmethod
    def delete_alarm(self, alarm_id):
        """Delete a alarm
        """

    @abc.abstractmethod
    def get_alarm_changes(self, alarm_id, on_behalf_of,
                          user=None, project=None, type=None,
                          start_timestamp=None, start_timestamp_op=None,
                          end_timestamp=None, end_timestamp_op=None):
        """Yields list of AlarmChanges describing alarm history

        Changes are always sorted in reverse order of occurence, given
        the importance of currency.

        Segregation for non-administrative users is done on the basis
        of the on_behalf_of parameter. This allows such users to have
        visibility on both the changes initiated by themselves directly
        (generally creation, rule changes, or deletion) and also on those
        changes initiated on their behalf by the alarming service (state
        transitions after alarm thresholds are crossed).

        :param alarm_id: ID of alarm to return changes for
        :param on_behalf_of: ID of tenant to scope changes query (None for
                             administrative user, indicating all projects)
        :param user: Optional ID of user to return changes for
        :param project: Optional ID of project to return changes for
        :project type: Optional change type
        :param start_timestamp: Optional modified timestamp start range
        :param start_timestamp_op: Optional timestamp start range operation
        :param end_timestamp: Optional modified timestamp end range
        :param end_timestamp_op: Optional timestamp end range operation
        """

    @abc.abstractmethod
    def record_alarm_change(self, alarm_change):
        """Record alarm change event.
        """

    @abc.abstractmethod
    def clear(self):
        """Clear database."""

    @abc.abstractmethod
    def record_events(self, events):
        """Write the events to the backend storage system.

        :param events: a list of model.Event objects.
        """

    @abc.abstractmethod
    def get_events(self, event_filter):
        """Return an iterable of model.Event objects.
        """
