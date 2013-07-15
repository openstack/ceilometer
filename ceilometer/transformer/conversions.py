# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc
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

from collections import defaultdict

from ceilometer import counter as ceilocounter
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer import transformer

LOG = log.getLogger(__name__)


class Namespace(object):
    """Encapsulates the namespace wrapping the evaluation of the
       configured scale factor. This allows nested dicts to be
       accessed in the attribute style, and missing attributes
       to yield false when used in a boolean expression.
    """
    def __init__(self, seed):
        self.__dict__ = defaultdict(lambda: Namespace({}))
        self.__dict__.update(seed)
        for k, v in self.__dict__.iteritems():
            if isinstance(v, dict):
                self.__dict__[k] = Namespace(v)

    def __getattr__(self, attr):
        return self.__dict__[attr]

    def __getitem__(self, key):
        return self.__dict__[key]

    def __nonzero__(self):
        return len(self.__dict__) > 0


class ScalingTransformer(transformer.TransformerBase):
    """Transformer to apply a scaling conversion.
    """

    def __init__(self, source={}, target={}, replace=False, **kwargs):
        """Initialize transformer with configured parameters.

        :param source: dict containing source counter unit
        :param target: dict containing target counter name, type,
                       unit and scaling factor (a missing value
                       connotes no change)
        :param replace: true if source counter is to be replaced
                        (as opposed to an additive conversion)
        """
        self.source = source
        self.target = target
        self.replace = replace
        self.preserved = None
        LOG.debug(_('scaling conversion transformer with source:'
                    ' %(source)s target: %(target)s replace:'
                    ' %(replace)s') % locals())
        super(ScalingTransformer, self).__init__(**kwargs)

    @staticmethod
    def _scale(counter, scale):
        """Apply the scaling factor (either a straight multiplicative
           factor or else a string to be eval'd).
        """
        ns = Namespace(counter._asdict())

        return ((eval(scale, {}, ns) if isinstance(scale, basestring)
                 else counter.volume * scale) if scale else counter.volume)

    def _convert(self, counter, growth=1):
        """Transform the appropriate counter fields.
        """
        scale = self.target.get('scale')
        return ceilocounter.Counter(
            name=self.target.get('name', counter.name),
            unit=self.target.get('unit', counter.unit),
            type=self.target.get('type', counter.type),
            volume=self._scale(counter, scale) * growth,
            user_id=counter.user_id,
            project_id=counter.project_id,
            resource_id=counter.resource_id,
            timestamp=counter.timestamp,
            resource_metadata=counter.resource_metadata
        )

    def _keep(self, counter, transformed):
        """Either replace counter with the transformed version
           or preserve for flush() call to emit as an additional
           sample.
        """
        if self.replace:
            counter = transformed
        else:
            self.preserved = transformed
        return counter

    def handle_sample(self, context, counter, source):
        """Handle a sample, converting if necessary."""
        LOG.debug('handling counter %s', (counter,))
        if (self.source.get('unit', counter.unit) == counter.unit):
            transformed = self._convert(counter)
            LOG.debug(_('converted to: %s') % (transformed,))
            counter = self._keep(counter, transformed)
        return counter

    def flush(self, context, source):
        """Emit the additional transformed counter in the non-replace
           case.
        """
        counters = []
        if self.preserved:
            counters.append(self.preserved)
            self.preserved = None
        return counters


class RateOfChangeTransformer(ScalingTransformer):
    """Transformer based on the rate of change of a counter volume,
       for example taking the current and previous volumes of a
       cumulative counter and producing a gauge value based on the
       proportion of some maximum used.
    """

    def __init__(self, **kwargs):
        """Initialize transformer with configured parameters.
        """
        self.cache = {}
        super(RateOfChangeTransformer, self).__init__(**kwargs)

    def handle_sample(self, context, counter, source):
        """Handle a sample, converting if necessary."""
        LOG.debug('handling counter %s', (counter,))
        key = counter.name + counter.resource_id
        prev = self.cache.get(key)
        timestamp = timeutils.parse_isotime(counter.timestamp)
        self.cache[key] = (counter.volume, timestamp)

        if prev:
            prev_volume = prev[0]
            prev_timestamp = prev[1]
            time_delta = timeutils.delta_seconds(prev_timestamp, timestamp)
            # we only allow negative deltas for noncumulative counters, whereas
            # for cumulative we assume that a reset has occurred in the interim
            # so that the current volume gives a lower bound on growth
            volume_delta = (counter.volume - prev_volume
                            if (prev_volume <= counter.volume or
                                counter.type != ceilocounter.TYPE_CUMULATIVE)
                            else counter.volume)
            rate_of_change = ((1.0 * volume_delta / time_delta)
                              if time_delta else 0.0)

            transformed = self._convert(counter, rate_of_change)
            LOG.debug(_('converted to: %s') % (transformed,))
            counter = self._keep(counter, transformed)
        elif self.replace:
            LOG.warn(_('dropping counter with no predecessor: %s') % counter)
            counter = None
        return counter
