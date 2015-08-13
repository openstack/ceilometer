#
# Copyright 2013 eNovance <licensing@enovance.com>
#
# Authors: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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


from oslo_log import log
from six import moves

from ceilometer.alarm import evaluator
from ceilometer.i18n import _

LOG = log.getLogger(__name__)

COMPARATORS = {'and': all, 'or': any}


class CombinationEvaluator(evaluator.Evaluator):

    def _get_alarm_state(self, alarm_id):
        try:
            alarm = self._client.alarms.get(alarm_id)
        except Exception:
            LOG.exception(_('alarm retrieval failed'))
            return None
        return alarm.state

    def _sufficient_states(self, alarm, states):
        """Check for the sufficiency of the data for evaluation.

        Ensure that there is sufficient data for evaluation,
        transitioning to unknown otherwise.
        """
        # note(sileht): alarm can be evaluated only with
        # stable state of other alarm
        alarms_missing_states = [alarm_id for alarm_id, state in states
                                 if not state or state == evaluator.UNKNOWN]
        sufficient = len(alarms_missing_states) == 0
        if not sufficient and alarm.rule['operator'] == 'or':
            # if operator is 'or' and there is one alarm, then the combinated
            # alarm's state should be 'alarm'
            sufficient = bool([alarm_id for alarm_id, state in states
                               if state == evaluator.ALARM])
        if not sufficient and alarm.state != evaluator.UNKNOWN:
            reason = (_('Alarms %(alarm_ids)s'
                        ' are in unknown state') %
                      {'alarm_ids': ",".join(alarms_missing_states)})
            reason_data = self._reason_data(alarms_missing_states)
            self._refresh(alarm, evaluator.UNKNOWN, reason, reason_data)
        return sufficient

    @staticmethod
    def _reason_data(alarm_ids):
        """Create a reason data dictionary for this evaluator type."""
        return {'type': 'combination', 'alarm_ids': alarm_ids}

    @classmethod
    def _reason(cls, alarm, state, underlying_states):
        """Fabricate reason string."""
        transition = alarm.state != state

        alarms_to_report = [alarm_id for alarm_id, alarm_state
                            in underlying_states
                            if alarm_state == state]
        reason_data = cls._reason_data(alarms_to_report)
        if transition:
            return (_('Transition to %(state)s due to alarms'
                      ' %(alarm_ids)s in state %(state)s') %
                    {'state': state,
                     'alarm_ids': ",".join(alarms_to_report)}), reason_data
        return (_('Remaining as %(state)s due to alarms'
                  ' %(alarm_ids)s in state %(state)s') %
                {'state': state,
                 'alarm_ids': ",".join(alarms_to_report)}), reason_data

    def _transition(self, alarm, underlying_states):
        """Transition alarm state if necessary."""
        op = alarm.rule['operator']
        if COMPARATORS[op](s == evaluator.ALARM
                           for __, s in underlying_states):
            state = evaluator.ALARM
        else:
            state = evaluator.OK

        continuous = alarm.repeat_actions
        reason, reason_data = self._reason(alarm, state, underlying_states)
        if alarm.state != state or continuous:
            self._refresh(alarm, state, reason, reason_data)

    def evaluate(self, alarm):
        if not self.within_time_constraint(alarm):
            LOG.debug('Attempted to evaluate alarm %s, but it is not '
                      'within its time constraint.', alarm.alarm_id)
            return

        states = zip(alarm.rule['alarm_ids'],
                     moves.map(self._get_alarm_state, alarm.rule['alarm_ids']))
        # states is consumed more than once, we need a list
        states = list(states)

        if self._sufficient_states(alarm, states):
            self._transition(alarm, states)
