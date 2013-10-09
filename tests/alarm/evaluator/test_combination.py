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
"""Tests for ceilometer/alarm/threshold_evaluation.py
"""
import mock
import uuid

from ceilometer.alarm.evaluator import combination
from ceilometer.storage import models
from ceilometerclient import exc
from ceilometerclient.v2 import alarms

from tests.alarm.evaluator import base


class TestEvaluate(base.TestEvaluatorBase):
    EVALUATOR = combination.CombinationEvaluator

    def prepare_alarms(self):
        self.alarms = [
            models.Alarm(name='or-alarm',
                         description='the or alarm',
                         type='combination',
                         enabled=True,
                         user_id='foobar',
                         project_id='snafu',
                         alarm_id=str(uuid.uuid4()),
                         state='insufficient data',
                         state_timestamp=None,
                         timestamp=None,
                         insufficient_data_actions=[],
                         ok_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         rule=dict(
                             alarm_ids=[
                                 '9cfc3e51-2ff1-4b1d-ac01-c1bd4c6d0d1e',
                                 '1d441595-d069-4e05-95ab-8693ba6a8302'],
                             operator='or',
                         )),
            models.Alarm(name='and-alarm',
                         description='the and alarm',
                         type='combination',
                         enabled=True,
                         user_id='foobar',
                         project_id='snafu',
                         alarm_id=str(uuid.uuid4()),
                         state='insufficient data',
                         state_timestamp=None,
                         timestamp=None,
                         insufficient_data_actions=[],
                         ok_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         rule=dict(
                             alarm_ids=[
                                 'b82734f4-9d06-48f3-8a86-fa59a0c99dc8',
                                 '15a700e5-2fe8-4b3d-8c55-9e92831f6a2b'],
                             operator='and',
                         ))
        ]

    @staticmethod
    def _get_alarm(state):
        return alarms.Alarm(None, {'state': state})

    def _combination_transition_reason(self, state):
        return ['Transition to %(state)s due at least to one alarm in'
                ' 9cfc3e51-2ff1-4b1d-ac01-c1bd4c6d0d1e,'
                '1d441595-d069-4e05-95ab-8693ba6a8302'
                ' in state %(state)s' % {'state': state},
                'Transition to %(state)s due to all alarms'
                ' (b82734f4-9d06-48f3-8a86-fa59a0c99dc8,'
                '15a700e5-2fe8-4b3d-8c55-9e92831f6a2b)'
                ' in state %(state)s' % {'state': state}]

    def _combination_remaining_reason(self, state):
        return ['Remaining as %(state)s due at least to one alarm in'
                ' 9cfc3e51-2ff1-4b1d-ac01-c1bd4c6d0d1e,'
                '1d441595-d069-4e05-95ab-8693ba6a8302'
                ' in state %(state)s' % {'state': state},
                'Remaining as %(state)s due to all alarms'
                ' (b82734f4-9d06-48f3-8a86-fa59a0c99dc8,'
                '15a700e5-2fe8-4b3d-8c55-9e92831f6a2b)'
                ' in state %(state)s' % {'state': state}]

    def test_retry_transient_api_failure(self):
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            broken = exc.CommunicationError(message='broken')
            self.api_client.alarms.get.side_effect = [
                broken,
                broken,
                broken,
                broken,
                self._get_alarm('ok'),
                self._get_alarm('ok'),
                self._get_alarm('ok'),
                self._get_alarm('ok'),
            ]
            self._evaluate_all_alarms()
            self._assert_all_alarms('insufficient data')
            self._evaluate_all_alarms()
            self._assert_all_alarms('ok')

    def test_simple_insufficient(self):
        self._set_all_alarms('ok')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            broken = exc.CommunicationError(message='broken')
            self.api_client.alarms.get.side_effect = broken
            self._evaluate_all_alarms()
            self._assert_all_alarms('insufficient data')
            expected = [mock.call(alarm.alarm_id, state='insufficient data')
                        for alarm in self.alarms]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)
            expected = [mock.call(alarm,
                                  'ok',
                                  ('%d alarms in %s are in unknown state' %
                                   (2, ",".join(alarm.rule['alarm_ids']))))
                        for alarm in self.alarms]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_to_ok_with_all_ok(self):
        self._set_all_alarms('insufficient data')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('ok'),
                self._get_alarm('ok'),
                self._get_alarm('ok'),
                self._get_alarm('ok'),
            ]
            self._evaluate_all_alarms()
            expected = [mock.call(alarm.alarm_id, state='ok')
                        for alarm in self.alarms]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)
            reasons = self._combination_transition_reason('ok')
            expected = [mock.call(alarm, 'insufficient data', reason)
                        for alarm, reason in zip(self.alarms, reasons)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_to_ok_with_one_alarm(self):
        self._set_all_alarms('alarm')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('ok'),
                self._get_alarm('ok'),
                self._get_alarm('alarm'),
                self._get_alarm('ok'),
            ]
            self._evaluate_all_alarms()
            expected = [mock.call(alarm.alarm_id, state='ok')
                        for alarm in self.alarms]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)
            reasons = self._combination_transition_reason('ok')
            expected = [mock.call(alarm, 'alarm', reason)
                        for alarm, reason in zip(self.alarms, reasons)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_to_alarm_with_all_alarm(self):
        self._set_all_alarms('ok')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('alarm'),
                self._get_alarm('alarm'),
                self._get_alarm('alarm'),
                self._get_alarm('alarm'),
            ]
            self._evaluate_all_alarms()
            expected = [mock.call(alarm.alarm_id, state='alarm')
                        for alarm in self.alarms]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)
            reasons = self._combination_transition_reason('alarm')
            expected = [mock.call(alarm, 'ok', reason)
                        for alarm, reason in zip(self.alarms, reasons)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_to_alarm_with_one_ok(self):
        self._set_all_alarms('ok')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('ok'),
                self._get_alarm('alarm'),
                self._get_alarm('alarm'),
                self._get_alarm('alarm'),
            ]
            self._evaluate_all_alarms()
            expected = [mock.call(alarm.alarm_id, state='alarm')
                        for alarm in self.alarms]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)
            reasons = self._combination_transition_reason('alarm')
            expected = [mock.call(alarm, 'ok', reason)
                        for alarm, reason in zip(self.alarms, reasons)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_to_unknown(self):
        self._set_all_alarms('ok')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            broken = exc.CommunicationError(message='broken')
            self.api_client.alarms.get.side_effect = [
                broken,
                self._get_alarm('ok'),
                self._get_alarm('insufficient data'),
                self._get_alarm('ok'),
            ]
            self._evaluate_all_alarms()
            expected = [mock.call(alarm.alarm_id, state='insufficient data')
                        for alarm in self.alarms]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)
            reasons = ['1 alarms in'
                       ' 9cfc3e51-2ff1-4b1d-ac01-c1bd4c6d0d1e,'
                       '1d441595-d069-4e05-95ab-8693ba6a8302'
                       ' are in unknown state',
                       '1 alarms in'
                       ' b82734f4-9d06-48f3-8a86-fa59a0c99dc8,'
                       '15a700e5-2fe8-4b3d-8c55-9e92831f6a2b'
                       ' are in unknown state']
            expected = [mock.call(alarm, 'ok', reason)
                        for alarm, reason in zip(self.alarms, reasons)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_no_state_change(self):
        self._set_all_alarms('ok')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('ok'),
                self._get_alarm('ok'),
                self._get_alarm('ok'),
                self._get_alarm('ok'),
            ]
            self._evaluate_all_alarms()
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, [])
            self.assertEqual(self.notifier.notify.call_args_list, [])

    def test_no_state_change_and_repeat_actions(self):
        self.alarms[0].repeat_actions = True
        self.alarms[1].repeat_actions = True
        self._set_all_alarms('ok')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.alarms.get.side_effect = [
                self._get_alarm('ok'),
                self._get_alarm('ok'),
                self._get_alarm('ok'),
                self._get_alarm('ok'),
            ]
            self._evaluate_all_alarms()
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, [])
            reasons = self._combination_remaining_reason('ok')
            expected = [mock.call(alarm, 'ok', reason)
                        for alarm, reason in zip(self.alarms, reasons)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)
