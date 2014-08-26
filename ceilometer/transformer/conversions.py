#
# Copyright 2013 Red Hat, Inc
#
# Author: Eoghan Glynn <eglynn@redhat.com>
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

import collections
import re

from oslo.utils import timeutils
import six

from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer import sample
from ceilometer import transformer

LOG = log.getLogger(__name__)


class ScalingTransformer(transformer.TransformerBase):
    """Transformer to apply a scaling conversion."""

    def __init__(self, source=None, target=None, **kwargs):
        """Initialize transformer with configured parameters.

        :param source: dict containing source sample unit
        :param target: dict containing target sample name, type,
                       unit and scaling factor (a missing value
                       connotes no change)
        """
        source = source or {}
        target = target or {}
        self.source = source
        self.target = target
        self.scale = target.get('scale')
        LOG.debug(_('scaling conversion transformer with source:'
                    ' %(source)s target: %(target)s:')
                  % {'source': source,
                     'target': target})
        super(ScalingTransformer, self).__init__(**kwargs)

    def _scale(self, s):
        """Apply the scaling factor.

        Either a straight multiplicative factor or else a string to be eval'd.
        """
        ns = transformer.Namespace(s.as_dict())

        scale = self.scale
        return ((eval(scale, {}, ns) if isinstance(scale, six.string_types)
                 else s.volume * scale) if scale else s.volume)

    def _map(self, s, attr):
        """Apply the name or unit mapping if configured."""
        mapped = None
        from_ = self.source.get('map_from')
        to_ = self.target.get('map_to')
        if from_ and to_:
            if from_.get(attr) and to_.get(attr):
                try:
                    mapped = re.sub(from_[attr], to_[attr], getattr(s, attr))
                except Exception:
                    pass
        return mapped or self.target.get(attr, getattr(s, attr))

    def _convert(self, s, growth=1):
        """Transform the appropriate sample fields."""
        return sample.Sample(
            name=self._map(s, 'name'),
            unit=self._map(s, 'unit'),
            type=self.target.get('type', s.type),
            volume=self._scale(s) * growth,
            user_id=s.user_id,
            project_id=s.project_id,
            resource_id=s.resource_id,
            timestamp=s.timestamp,
            resource_metadata=s.resource_metadata
        )

    def handle_sample(self, context, s):
        """Handle a sample, converting if necessary."""
        LOG.debug(_('handling sample %s'), (s,))
        if self.source.get('unit', s.unit) == s.unit:
            s = self._convert(s)
            LOG.debug(_('converted to: %s'), (s,))
        return s


class RateOfChangeTransformer(ScalingTransformer):
    """Transformer based on the rate of change of a sample volume.

    For example taking the current and previous volumes of a cumulative sample
    and producing a gauge value based on the proportion of some maximum used.
    """

    def __init__(self, **kwargs):
        """Initialize transformer with configured parameters."""
        super(RateOfChangeTransformer, self).__init__(**kwargs)
        self.cache = {}
        self.scale = self.scale or '1'

    def handle_sample(self, context, s):
        """Handle a sample, converting if necessary."""
        LOG.debug(_('handling sample %s'), (s,))
        key = s.name + s.resource_id
        prev = self.cache.get(key)
        timestamp = timeutils.parse_isotime(s.timestamp)
        self.cache[key] = (s.volume, timestamp)

        if prev:
            prev_volume = prev[0]
            prev_timestamp = prev[1]
            time_delta = timeutils.delta_seconds(prev_timestamp, timestamp)
            # we only allow negative deltas for noncumulative samples, whereas
            # for cumulative we assume that a reset has occurred in the interim
            # so that the current volume gives a lower bound on growth
            volume_delta = (s.volume - prev_volume
                            if (prev_volume <= s.volume or
                                s.type != sample.TYPE_CUMULATIVE)
                            else s.volume)
            rate_of_change = ((1.0 * volume_delta / time_delta)
                              if time_delta else 0.0)

            s = self._convert(s, rate_of_change)
            LOG.debug(_('converted to: %s'), (s,))
        else:
            LOG.warn(_('dropping sample with no predecessor: %s'),
                     (s,))
            s = None
        return s


class AggregatorTransformer(ScalingTransformer):
    """Transformer that aggregates samples.

    Aggregation goes until a threshold or/and a retention_time, and then
    flushes them out into the wild.

    Example:
      To aggregate sample by resource_metadata and keep the
      resource_metadata of the latest received sample;

        AggregatorTransformer(retention_time=60, resource_metadata='last')

      To aggregate sample by user_id and resource_metadata and keep the
      user_id of the first received sample and drop the resource_metadata.

        AggregatorTransformer(size=15, user_id='first',
                              resource_metadata='drop')
    """

    def __init__(self, size=1, retention_time=None,
                 project_id=None, user_id=None, resource_metadata="last",
                 **kwargs):
        super(AggregatorTransformer, self).__init__(**kwargs)
        self.samples = {}
        self.counts = collections.defaultdict(int)
        self.size = int(size) if size else None
        self.retention_time = float(retention_time) if retention_time else None
        self.initial_timestamp = None
        self.aggregated_samples = 0

        self.key_attributes = []
        self.merged_attribute_policy = {}

        self._init_attribute('project_id', project_id)
        self._init_attribute('user_id', user_id)
        self._init_attribute('resource_metadata', resource_metadata,
                             is_droppable=True, mandatory=True)

    def _init_attribute(self, name, value, is_droppable=False,
                        mandatory=False):
        drop = ['drop'] if is_droppable else []
        if value or mandatory:
            if value not in ['last', 'first'] + drop:
                LOG.warn('%s is unknown (%s), using last' % (name, value))
                value = 'last'
            self.merged_attribute_policy[name] = value
        else:
            self.key_attributes.append(name)

    def _get_unique_key(self, s):
        # NOTE(arezmerita): in samples generated by ceilometer middleware,
        # when accessing without authentication publicly readable/writable
        # swift containers, the project_id and the user_id are missing.
        # They will be replaced by <undefined> for unique key construction.
        keys = ['<undefined>' if getattr(s, f) is None else getattr(s, f)
                for f in self.key_attributes]
        non_aggregated_keys = "-".join(keys)
        # NOTE(sileht): it assumes, a meter always have the same unit/type
        return "%s-%s-%s" % (s.name, s.resource_id, non_aggregated_keys)

    def handle_sample(self, context, sample_):
        if not self.initial_timestamp:
            self.initial_timestamp = timeutils.parse_isotime(sample_.timestamp)

        self.aggregated_samples += 1
        key = self._get_unique_key(sample_)
        self.counts[key] += 1
        if key not in self.samples:
            self.samples[key] = self._convert(sample_)
            if self.merged_attribute_policy[
                    'resource_metadata'] == 'drop':
                self.samples[key].resource_metadata = {}
        else:
            if sample_.type == sample.TYPE_CUMULATIVE:
                self.samples[key].volume = self._scale(sample_)
            else:
                self.samples[key].volume += self._scale(sample_)
            for field in self.merged_attribute_policy:
                if self.merged_attribute_policy[field] == 'last':
                    setattr(self.samples[key], field,
                            getattr(sample_, field))

    def flush(self, context):
        if not self.initial_timestamp:
            return []

        expired = (self.retention_time and
                   timeutils.is_older_than(self.initial_timestamp,
                                           self.retention_time))
        full = self.aggregated_samples >= self.size
        if full or expired:
            x = self.samples.values()
            # gauge aggregates need to be averages
            for s in x:
                if s.type == sample.TYPE_GAUGE:
                    key = self._get_unique_key(s)
                    s.volume /= self.counts[key]
            self.samples.clear()
            self.counts.clear()
            self.aggregated_samples = 0
            self.initial_timestamp = None
            return x
        return []
