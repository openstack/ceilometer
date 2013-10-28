# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
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


from ceilometer.alarm import evaluator
from ceilometer.alarm.evaluator import OK, ALARM, UNKNOWN
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log

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
        """Ensure there is sufficient data for evaluation,
        transitioning to unknown otherwise.
        """
        missing_states = len(alarm.rule['alarm_ids']) - len(states)
        sufficient = missing_states == 0
        if not sufficient and alarm.state != UNKNOWN:
            reason = _('%(missing_states)d alarms in %(alarm_ids)s'
                       ' are in unknown state') % \
                {'missing_states': missing_states,
                 'alarm_ids': ",".join(alarm.rule['alarm_ids'])}
            self._refresh(alarm, UNKNOWN, reason)
        return sufficient

    @staticmethod
    def _reason(alarm, state):
        """Fabricate reason string."""
        transition = alarm.state != state
        if alarm.rule['operator'] == 'or':
            if transition:
                return (_('Transition to %(state)s due at least to one alarm'
                          ' in %(alarm_ids)s in state %(state)s') %
                        {'state': state,
                         'alarm_ids': ",".join(alarm.rule['alarm_ids'])})
            return (_('Remaining as %(state)s due at least to one alarm in'
                      ' %(alarm_ids)s in state %(state)s') %
                    {'state': state,
                     'alarm_ids': ",".join(alarm.rule['alarm_ids'])})
        elif alarm.rule['operator'] == 'and':
            if transition:
                return (_('Transition to %(state)s due to all alarms'
                          ' (%(alarm_ids)s) in state %(state)s') %
                        {'state': state,
                         'alarm_ids': ",".join(alarm.rule['alarm_ids'])})
            return (_('Remaining as %(state)s due to all alarms'
                      ' (%(alarm_ids)s) in state %(state)s') %
                    {'state': state,
                     'alarm_ids': ",".join(alarm.rule['alarm_ids'])})

    def _transition(self, alarm, underlying_states):
        """Transition alarm state if necessary.
        """
        op = alarm.rule['operator']
        if COMPARATORS[op](s == ALARM for s in underlying_states):
            state = ALARM
        else:
            state = OK

        continuous = alarm.repeat_actions
        reason = self._reason(alarm, state)
        if alarm.state != state or continuous:
            self._refresh(alarm, state, reason)

    def evaluate(self, alarm):
        states = []
        for _id in alarm.rule['alarm_ids']:
            state = self._get_alarm_state(_id)
            #note(sileht): alarm can be evaluated only with
            #stable state of other alarm
            if state and state != UNKNOWN:
                states.append(state)

        if self._sufficient_states(alarm, states):
            self._transition(alarm, states)
