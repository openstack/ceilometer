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

import pecan
import wsme
from wsme import types as wtypes

from ceilometer.api.controllers.v2 import base
from ceilometer.api.controllers.v2 import utils as v2_utils
from ceilometer.i18n import _


class AlarmCombinationRule(base.AlarmRule):
    """Alarm Combinarion Rule

    Describe when to trigger the alarm based on combining the state of
    other alarms.
    """

    operator = base.AdvEnum('operator', str, 'or', 'and', default='and')
    "How to combine the sub-alarms"

    alarm_ids = wsme.wsattr([wtypes.text], mandatory=True)
    "List of alarm identifiers to combine"

    @property
    def default_description(self):
        joiner = ' %s ' % self.operator
        return _('Combined state of alarms %s') % joiner.join(self.alarm_ids)

    def as_dict(self):
        return self.as_dict_from_keys(['operator', 'alarm_ids'])

    @staticmethod
    def validate(rule):
        rule.alarm_ids = sorted(set(rule.alarm_ids), key=rule.alarm_ids.index)
        if len(rule.alarm_ids) <= 1:
            raise base.ClientSideError(_('Alarm combination rule should '
                                         'contain at least two different '
                                         'alarm ids.'))
        return rule

    @staticmethod
    def validate_alarm(alarm):
        project = v2_utils.get_auth_project(
            alarm.project_id if alarm.project_id != wtypes.Unset else None)
        for id in alarm.combination_rule.alarm_ids:
            alarms = list(pecan.request.alarm_storage_conn.get_alarms(
                alarm_id=id, project=project))
            if not alarms:
                raise base.AlarmNotFound(id, project)

    @staticmethod
    def update_hook(alarm):
        # should check if there is any circle in the dependency, but for
        # efficiency reason, here only check alarm cannot depend on itself
        if alarm.alarm_id in alarm.combination_rule.alarm_ids:
            raise base.ClientSideError(
                _('Cannot specify alarm %s itself in combination rule') %
                alarm.alarm_id)

    @classmethod
    def sample(cls):
        return cls(operator='or',
                   alarm_ids=['739e99cb-c2ec-4718-b900-332502355f38',
                              '153462d0-a9b8-4b5b-8175-9e4b05e9b856'])
