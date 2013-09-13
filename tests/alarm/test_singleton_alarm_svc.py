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
"""Tests for ceilometer/alarm/service.py
"""
import mock

from stevedore import extension
from stevedore.tests import manager as extension_tests

from ceilometer.alarm import service
from ceilometer.tests import base


class TestSingletonAlarmService(base.TestCase):
    def setUp(self):
        super(TestSingletonAlarmService, self).setUp()
        self.threshold_eval = mock.Mock()
        self.evaluators = extension_tests.TestExtensionManager(
            [
                extension.Extension(
                    'threshold',
                    None,
                    None,
                    self.threshold_eval),
            ])
        self.api_client = mock.MagicMock()
        self.singleton = service.SingletonAlarmService()
        self.singleton.tg = mock.Mock()
        self.singleton.evaluators = self.evaluators
        self.singleton.supported_evaluators = ['threshold']

    def test_start(self):
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.singleton.start()
            expected = [
                mock.call(60,
                          self.singleton._evaluate_all_alarms,
                          0),
                mock.call(604800, mock.ANY),
            ]
            actual = self.singleton.tg.add_timer.call_args_list
            self.assertEqual(actual, expected)

    def test_evaluation_cycle(self):
        alarm = mock.Mock(enabled=True,
                          type='threshold')
        self.api_client.alarms.list.return_value = [alarm]
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.singleton._evaluate_all_alarms()
            self.threshold_eval.evaluate.assert_called_once_with(alarm)

    def test_disabled_is_skipped(self):
        alarms = [
            mock.Mock(enabled=False,
                      type='threshold'),
            mock.Mock(enabled=True,
                      type='threshold'),
        ]

        self.api_client.alarms.list.return_value = alarms
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.singleton.start()
            self.singleton._evaluate_all_alarms()
            self.threshold_eval.evaluate.assert_called_once_with(alarms[1])

    def test_unknown_extention_skipped(self):
        alarms = [
            mock.Mock(type='not_existing_type'),
            mock.Mock(type='threshold')
        ]

        self.api_client.alarms.list.return_value = alarms
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.singleton.start()
            self.singleton._evaluate_all_alarms()
            self.threshold_eval.evaluate.assert_called_once_with(alarms[1])
