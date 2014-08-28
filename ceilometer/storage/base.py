#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

import datetime
import inspect
import math

from oslo.utils import timeutils
import six
from six import moves


def iter_period(start, end, period):
    """Split a time from start to end in periods of a number of seconds.

    This function yields the (start, end) time for each period composing the
    time passed as argument.

    :param start: When the period set start.
    :param end: When the period end starts.
    :param period: The duration of the period.
    """
    period_start = start
    increment = datetime.timedelta(seconds=period)
    for i in moves.xrange(int(math.ceil(
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
    # in the first place of sort keys list.
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

    def __init__(self, limit=None, primary_sort_dir='desc', sort_keys=None,
                 sort_dirs=None, marker_value=None):
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
        self.sort_keys = sort_keys or []
        self.sort_dirs = sort_dirs or []


class Model(object):
    """Base class for storage API models."""

    def __init__(self, **kwds):
        self.fields = list(kwds)
        for k, v in six.iteritems(kwds):
            setattr(self, k, v)

    def as_dict(self):
        d = {}
        for f in self.fields:
            v = getattr(self, f)
            if isinstance(v, Model):
                v = v.as_dict()
            elif isinstance(v, list) and v and isinstance(v[0], Model):
                v = [sub.as_dict() for sub in v]
            d[f] = v
        return d

    def __eq__(self, other):
        return self.as_dict() == other.as_dict()

    @classmethod
    def get_field_names(cls):
        fields = inspect.getargspec(cls.__init__)[0]
        return set(fields) - set(["self"])


class Connection(object):
    """Base class for storage system connections."""

    # A dictionary representing the capabilities of this driver.
    CAPABILITIES = {
        'meters': {'pagination': False,
                   'query': {'simple': False,
                             'metadata': False,
                             'complex': False}},
        'resources': {'pagination': False,
                      'query': {'simple': False,
                                'metadata': False,
                                'complex': False}},
        'samples': {'pagination': False,
                    'groupby': False,
                    'query': {'simple': False,
                              'metadata': False,
                              'complex': False}},
        'statistics': {'pagination': False,
                       'groupby': False,
                       'query': {'simple': False,
                                 'metadata': False,
                                 'complex': False},
                       'aggregation': {'standard': False,
                                       'selectable': {
                                           'max': False,
                                           'min': False,
                                           'sum': False,
                                           'avg': False,
                                           'count': False,
                                           'stddev': False,
                                           'cardinality': False}}
                       },
        'events': {'query': {'simple': False}},
    }

    STORAGE_CAPABILITIES = {
        'storage': {'production_ready': False},
    }

    def __init__(self, url):
        """Constructor."""
        pass

    @staticmethod
    def upgrade():
        """Migrate the database to `version` or the most recent version."""

    @staticmethod
    def record_metering_data(data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter

        All timestamps must be naive utc datetime object.
        """
        raise NotImplementedError('Projects not implemented')

    @staticmethod
    def clear_expired_metering_data(ttl):
        """Clear expired data from the backend storage system.

        Clearing occurs according to the time-to-live.

        :param ttl: Number of seconds to keep records for.
        """
        raise NotImplementedError('Clearing samples not implemented')

    @staticmethod
    def get_resources(user=None, project=None, source=None,
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None,
                      metaquery=None, resource=None, pagination=None):
        """Return an iterable of models.Resource instances.

        Iterable items containing resource information.
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
        raise NotImplementedError('Resources not implemented')

    @staticmethod
    def get_meters(user=None, project=None, resource=None, source=None,
                   metaquery=None, pagination=None):
        """Return an iterable of model.Meter instances.

        Iterable items containing meter information.
        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional resource filter.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param pagination: Optional pagination query.
        """
        raise NotImplementedError('Meters not implemented')

    @staticmethod
    def get_samples(sample_filter, limit=None):
        """Return an iterable of model.Sample instances.

        :param sample_filter: Filter.
        :param limit: Maximum number of results to return.
        """
        raise NotImplementedError('Samples not implemented')

    @staticmethod
    def get_meter_statistics(sample_filter, period=None, groupby=None,
                             aggregate=None):
        """Return an iterable of model.Statistics instances.

        The filter must have a meter value set.
        """
        raise NotImplementedError('Statistics not implemented')

    @staticmethod
    def clear():
        """Clear database."""

    @staticmethod
    def record_events(events):
        """Write the events to the backend storage system.

        :param events: a list of model.Event objects.
        """
        raise NotImplementedError('Events not implemented.')

    @staticmethod
    def get_events(event_filter):
        """Return an iterable of model.Event objects."""
        raise NotImplementedError('Events not implemented.')

    @staticmethod
    def get_event_types():
        """Return all event types as an iterable of strings."""
        raise NotImplementedError('Events not implemented.')

    @staticmethod
    def get_trait_types(event_type):
        """Return a dictionary containing the name and data type of the trait.

        Only trait types for the provided event_type are
        returned.
        :param event_type: the type of the Event
        """
        raise NotImplementedError('Events not implemented.')

    @staticmethod
    def get_traits(event_type, trait_type=None):
        """Return all trait instances associated with an event_type.

        If trait_type is specified, only return instances of that trait type.
        :param event_type: the type of the Event to filter by
        :param trait_type: the name of the Trait to filter by
        """

        raise NotImplementedError('Events not implemented.')

    @staticmethod
    def query_samples(filter_expr=None, orderby=None, limit=None):
        """Return an iterable of model.Sample objects.

        :param filter_expr: Filter expression for query.
        :param orderby: List of field name and direction pairs for order by.
        :param limit: Maximum number of results to return.
        """

        raise NotImplementedError('Complex query for samples '
                                  'is not implemented.')

    @classmethod
    def get_capabilities(cls):
        """Return an dictionary with the capabilities of each driver."""
        return cls.CAPABILITIES

    @classmethod
    def get_storage_capabilities(cls):
        """Return a dictionary representing the performance capabilities.

        This is needed to evaluate the performance of each driver.
        """
        return cls.STORAGE_CAPABILITIES
