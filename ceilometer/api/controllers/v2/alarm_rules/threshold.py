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

import wsme
from wsme import types as wtypes

from ceilometer.api.controllers.v2 import base
from ceilometer.api.controllers.v2 import utils as v2_utils
from ceilometer.i18n import _
from ceilometer import storage


class AlarmThresholdRule(base.AlarmRule):
    """Alarm Threshold Rule

    Describe when to trigger the alarm based on computed statistics
    """

    meter_name = wsme.wsattr(wtypes.text, mandatory=True)
    "The name of the meter"

    # FIXME(sileht): default doesn't work
    # workaround: default is set in validate method
    query = wsme.wsattr([base.Query], default=[])
    """The query to find the data for computing statistics.
    Ownership settings are automatically included based on the Alarm owner.
    """

    period = wsme.wsattr(wtypes.IntegerType(minimum=1), default=60)
    "The time range in seconds over which query"

    comparison_operator = base.AdvEnum('comparison_operator', str,
                                       'lt', 'le', 'eq', 'ne', 'ge', 'gt',
                                       default='eq')
    "The comparison against the alarm threshold"

    threshold = wsme.wsattr(float, mandatory=True)
    "The threshold of the alarm"

    statistic = base.AdvEnum('statistic', str, 'max', 'min', 'avg', 'sum',
                             'count', default='avg')
    "The statistic to compare to the threshold"

    evaluation_periods = wsme.wsattr(wtypes.IntegerType(minimum=1), default=1)
    "The number of historical periods to evaluate the threshold"

    exclude_outliers = wsme.wsattr(bool, default=False)
    "Whether datapoints with anomalously low sample counts are excluded"

    def __init__(self, query=None, **kwargs):
        if query:
            query = [base.Query(**q) for q in query]
        super(AlarmThresholdRule, self).__init__(query=query, **kwargs)

    @staticmethod
    def validate(threshold_rule):
        # note(sileht): wsme default doesn't work in some case
        # workaround for https://bugs.launchpad.net/wsme/+bug/1227039
        if not threshold_rule.query:
            threshold_rule.query = []

        # Timestamp is not allowed for AlarmThresholdRule query, as the alarm
        # evaluator will construct timestamp bounds for the sequence of
        # statistics queries as the sliding evaluation window advances
        # over time.
        v2_utils.validate_query(threshold_rule.query,
                                storage.SampleFilter.__init__,
                                allow_timestamps=False)
        return threshold_rule

    @staticmethod
    def validate_alarm(alarm):
        # ensure an implicit constraint on project_id is added to
        # the query if not already present
        alarm.threshold_rule.query = v2_utils.sanitize_query(
            alarm.threshold_rule.query,
            storage.SampleFilter.__init__,
            on_behalf_of=alarm.project_id
        )

    @property
    def default_description(self):
        return (_('Alarm when %(meter_name)s is %(comparison_operator)s a '
                  '%(statistic)s of %(threshold)s over %(period)s seconds') %
                dict(comparison_operator=self.comparison_operator,
                     statistic=self.statistic,
                     threshold=self.threshold,
                     meter_name=self.meter_name,
                     period=self.period))

    def as_dict(self):
        rule = self.as_dict_from_keys(['period', 'comparison_operator',
                                       'threshold', 'statistic',
                                       'evaluation_periods', 'meter_name',
                                       'exclude_outliers'])
        rule['query'] = [q.as_dict() for q in self.query]
        return rule

    @classmethod
    def sample(cls):
        return cls(meter_name='cpu_util',
                   period=60,
                   evaluation_periods=1,
                   threshold=300.0,
                   statistic='avg',
                   comparison_operator='gt',
                   query=[{'field': 'resource_id',
                           'value': '2a4d689b-f0b8-49c1-9eef-87cae58d80db',
                           'op': 'eq',
                           'type': 'string'}])
