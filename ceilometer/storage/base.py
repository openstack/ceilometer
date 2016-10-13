#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

from oslo_utils import timeutils
import six
from six import moves

import ceilometer


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

    :param model_name: Database model name be query.(meter, etc.)
    :param sort_key: sort key passed from user.
    return: sort keys list
    """
    sort_keys_extra = {'meter': ['user_id', 'project_id'],
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

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def get_field_names(cls):
        fields = inspect.getargspec(cls.__init__)[0]
        return set(fields) - set(["self"])


class Connection(object):
    """Base class for storage system connections."""

    # A dictionary representing the capabilities of this driver.
    CAPABILITIES = {
        'meters': {'query': {'simple': False,
                             'metadata': False}},
        'resources': {'query': {'simple': False,
                                'metadata': False}},
        'samples': {'query': {'simple': False,
                              'metadata': False,
                              'complex': False}},
        'statistics': {'groupby': False,
                       'query': {'simple': False,
                                 'metadata': False},
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
    }

    STORAGE_CAPABILITIES = {
        'storage': {'production_ready': False},
    }

    def __init__(self, conf, url):
        self.conf = conf

    @staticmethod
    def upgrade():
        """Migrate the database to `version` or the most recent version."""

    def record_metering_data_batch(self, samples):
        """Record the metering data in batch"""
        for s in samples:
            self.record_metering_data(s)

    @staticmethod
    def record_metering_data(data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.publisher.utils.meter_message_from_counter

        All timestamps must be naive utc datetime object.
        """
        raise ceilometer.NotImplementedError(
            'Recording metering data is not implemented')

    @staticmethod
    def clear_expired_metering_data(ttl):
        """Clear expired data from the backend storage system.

        Clearing occurs according to the time-to-live.

        :param ttl: Number of seconds to keep records for.
        """
        raise ceilometer.NotImplementedError(
            'Clearing samples not implemented')

    @staticmethod
    def get_resources(user=None, project=None, source=None,
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None,
                      metaquery=None, resource=None, limit=None):
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
        :param limit: Maximum number of results to return.
        """
        raise ceilometer.NotImplementedError('Resources not implemented')

    @staticmethod
    def get_meters(user=None, project=None, resource=None, source=None,
                   metaquery=None, limit=None, unique=False):
        """Return an iterable of model.Meter instances.

        Iterable items containing meter information.
        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional resource filter.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param limit: Maximum number of results to return.
        :param unique: If set to true, return only unique meter information.
        """
        raise ceilometer.NotImplementedError('Meters not implemented')

    @staticmethod
    def get_samples(sample_filter, limit=None):
        """Return an iterable of model.Sample instances.

        :param sample_filter: Filter.
        :param limit: Maximum number of results to return.
        """
        raise ceilometer.NotImplementedError('Samples not implemented')

    @staticmethod
    def get_meter_statistics(sample_filter, period=None, groupby=None,
                             aggregate=None):
        """Return an iterable of model.Statistics instances.

        The filter must have a meter value set.
        """
        raise ceilometer.NotImplementedError('Statistics not implemented')

    @staticmethod
    def clear():
        """Clear database."""

    @staticmethod
    def query_samples(filter_expr=None, orderby=None, limit=None):
        """Return an iterable of model.Sample objects.

        :param filter_expr: Filter expression for query.
        :param orderby: List of field name and direction pairs for order by.
        :param limit: Maximum number of results to return.
        """

        raise ceilometer.NotImplementedError('Complex query for samples '
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
