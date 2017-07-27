#
# Copyright 2014 Red Hat, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import collections
import copy
import keyword
import math
import re

from oslo_log import log
import six

from ceilometer.i18n import _
from ceilometer import sample
from ceilometer import transformer

LOG = log.getLogger(__name__)


class ArithmeticTransformer(transformer.TransformerBase):
    """Multi meter arithmetic transformer.

    Transformer that performs arithmetic operations
    over one or more meters and/or their metadata.
    """

    grouping_keys = ['resource_id']

    meter_name_re = re.compile(r'\$\(([\w\.\-]+)\)')

    def __init__(self, target=None, **kwargs):
        super(ArithmeticTransformer, self).__init__(**kwargs)
        target = target or {}
        self.target = target
        self.expr = target.get('expr', '')
        self.expr_escaped, self.escaped_names = self.parse_expr(self.expr)
        self.required_meters = list(self.escaped_names.values())
        self.misconfigured = len(self.required_meters) == 0
        if not self.misconfigured:
            self.reference_meter = self.required_meters[0]
            # convert to set for more efficient contains operation
            self.required_meters = set(self.required_meters)
            self.cache = collections.defaultdict(dict)
            self.latest_timestamp = None
        else:
            LOG.warning(_('Arithmetic transformer must use at least one'
                        ' meter in expression \'%s\''), self.expr)

    def _update_cache(self, _sample):
        """Update the cache with the latest sample."""
        escaped_name = self.escaped_names.get(_sample.name, '')
        if escaped_name not in self.required_meters:
            return
        self.cache[_sample.resource_id][escaped_name] = _sample

    def _check_requirements(self, resource_id):
        """Check if all the required meters are available in the cache."""
        return len(self.cache[resource_id]) == len(self.required_meters)

    def _calculate(self, resource_id):
        """Evaluate the expression and return a new sample if successful."""
        ns_dict = dict((m, s.as_dict()) for m, s
                       in six.iteritems(self.cache[resource_id]))
        ns = transformer.Namespace(ns_dict)
        try:
            new_volume = eval(self.expr_escaped, {}, ns)
            if math.isnan(new_volume):
                raise ArithmeticError(_('Expression evaluated to '
                                        'a NaN value!'))

            reference_sample = self.cache[resource_id][self.reference_meter]
            return sample.Sample(
                name=self.target.get('name', reference_sample.name),
                unit=self.target.get('unit', reference_sample.unit),
                type=self.target.get('type', reference_sample.type),
                volume=float(new_volume),
                user_id=reference_sample.user_id,
                project_id=reference_sample.project_id,
                resource_id=reference_sample.resource_id,
                timestamp=self.latest_timestamp,
                resource_metadata=reference_sample.resource_metadata
            )
        except Exception as e:
            LOG.warning(_('Unable to evaluate expression %(expr)s: %(exc)s'),
                        {'expr': self.expr, 'exc': e})

    def handle_sample(self, _sample):
        self._update_cache(_sample)
        self.latest_timestamp = _sample.timestamp

    def flush(self):
        new_samples = []
        if not self.misconfigured:
            # When loop self.cache, the dict could not be change by others.
            # If changed, will raise "RuntimeError: dictionary changed size
            # during iteration". so we make a tmp copy and just loop it.
            tmp_cache = copy.copy(self.cache)
            for resource_id in tmp_cache:
                if self._check_requirements(resource_id):
                    new_samples.append(self._calculate(resource_id))
                    if resource_id in self.cache:
                        self.cache.pop(resource_id)
        return new_samples

    @classmethod
    def parse_expr(cls, expr):
        """Transforms meter names in the expression into valid identifiers.

        :param expr: unescaped expression
        :return: A tuple of the escaped expression and a dict representing
                 the translation of meter names into Python identifiers
        """

        class Replacer(object):
            """Replaces matched meter names with escaped names.

            If the meter name is not followed by parameter access in the
            expression, it defaults to accessing the 'volume' parameter.
            """

            def __init__(self, original_expr):
                self.original_expr = original_expr
                self.escaped_map = {}

            def __call__(self, match):
                meter_name = match.group(1)
                escaped_name = self.escape(meter_name)
                self.escaped_map[meter_name] = escaped_name

                if (match.end(0) == len(self.original_expr) or
                        self.original_expr[match.end(0)] != '.'):
                    escaped_name += '.volume'
                return escaped_name

            @staticmethod
            def escape(name):
                has_dot = '.' in name
                if has_dot:
                    name = name.replace('.', '_')

                if has_dot or name.endswith('ESC') or name in keyword.kwlist:
                    name = "_" + name + '_ESC'
                return name

        replacer = Replacer(expr)
        expr = re.sub(cls.meter_name_re, replacer, expr)
        return expr, replacer.escaped_map
