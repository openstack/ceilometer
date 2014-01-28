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
"""Tests for ceilometer.alarm.service.SingletonAlarmService.
"""
import mock

from oslo.config import cfg

from stevedore import extension

from ceilometer.alarm import service
from ceilometer.openstack.common import test


class TestSingletonAlarmService(test.BaseTestCase):
    def setUp(self):
        super(TestSingletonAlarmService, self).setUp()
        self.threshold_eval = mock.Mock()
        self.evaluators = extension.ExtensionManager.make_test_instance(
            [
                extension.Extension(
                    'threshold',
                    None,
                    None,
                    self.threshold_eval),
            ]
        )
        self.api_client = mock.MagicMock()
        self.singleton = service.SingletonAlarmService()
        self.singleton.tg = mock.Mock()
        self.singleton.evaluators = self.evaluators
        self.singleton.supported_evaluators = ['threshold']

    def test_start(self):
        test_interval = 120
        cfg.CONF.set_override('evaluation_interval',
                              test_interval,
                              group='alarm')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.singleton.start()
            expected = [
                mock.call(test_interval,
                          self.singleton._evaluate_assigned_alarms,
                          0),
                mock.call(604800, mock.ANY),
            ]
            actual = self.singleton.tg.add_timer.call_args_list
            self.assertEqual(actual, expected)

    def test_evaluation_cycle(self):
        alarm = mock.Mock(type='threshold')
        self.api_client.alarms.list.return_value = [alarm]
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.singleton._evaluate_assigned_alarms()
            self.threshold_eval.evaluate.assert_called_once_with(alarm)

    def test_unknown_extension_skipped(self):
        alarms = [
            mock.Mock(type='not_existing_type'),
            mock.Mock(type='threshold')
        ]

        self.api_client.alarms.list.return_value = alarms
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.singleton.start()
            self.singleton._evaluate_assigned_alarms()
            self.threshold_eval.evaluate.assert_called_once_with(alarms[1])

    def test_singleton_endpoint_types(self):
        endpoint_types = ["internalURL", "publicURL"]
        for endpoint_type in endpoint_types:
            cfg.CONF.set_override('os_endpoint_type',
                                  endpoint_type,
                                  group='service_credentials')
            with mock.patch('ceilometerclient.client.get_client') as client:
                self.singleton.api_client = None
                self.singleton._evaluate_assigned_alarms()
                conf = cfg.CONF.service_credentials
                expected = [mock.call(2,
                                      os_auth_url=conf.os_auth_url,
                                      os_region_name=conf.os_region_name,
                                      os_tenant_name=conf.os_tenant_name,
                                      os_password=conf.os_password,
                                      os_username=conf.os_username,
                                      os_cacert=conf.os_cacert,
                                      os_endpoint_type=conf.os_endpoint_type)]
                actual = client.call_args_list
                self.assertEqual(actual, expected)
