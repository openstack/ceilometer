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
"""Tests for ceilometer.alarm.service.SingletonAlarmService.
"""
import mock
from oslo.config import fixture as fixture_config
from stevedore import extension

from ceilometer.alarm import service
from ceilometer.tests import base as tests_base


class TestAlarmEvaluationService(tests_base.BaseTestCase):
    def setUp(self):
        super(TestAlarmEvaluationService, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.setup_messaging(self.CONF)

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
        self.svc = service.AlarmEvaluationService()
        self.svc.tg = mock.Mock()
        self.svc.partition_coordinator = mock.MagicMock()
        p_coord = self.svc.partition_coordinator
        p_coord.extract_my_subset.side_effect = lambda _, x: x
        self.svc.evaluators = self.evaluators
        self.svc.supported_evaluators = ['threshold']

    def _do_test_start(self, test_interval=120,
                       coordination_heartbeat=1.0,
                       coordination_active=False):
        self.CONF.set_override('evaluation_interval',
                               test_interval,
                               group='alarm')
        self.CONF.set_override('heartbeat',
                               coordination_heartbeat,
                               group='coordination')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            p_coord_mock = self.svc.partition_coordinator
            p_coord_mock.is_active.return_value = coordination_active

            self.svc.start()
            self.svc.partition_coordinator.start.assert_called_once_with()
            self.svc.partition_coordinator.join_group.assert_called_once_with(
                self.svc.PARTITIONING_GROUP_NAME)

            initial_delay = test_interval if coordination_active else None
            expected = [
                mock.call(test_interval,
                          self.svc._evaluate_assigned_alarms,
                          initial_delay=initial_delay),
                mock.call(604800, mock.ANY),
            ]
            if coordination_active:
                hb_interval = min(coordination_heartbeat, test_interval / 4)
                hb_call = mock.call(hb_interval,
                                    self.svc.partition_coordinator.heartbeat)
                expected.insert(1, hb_call)
            actual = self.svc.tg.add_timer.call_args_list
            self.assertEqual(expected, actual)

    def test_start_singleton(self):
        self._do_test_start(coordination_active=False)

    def test_start_coordinated(self):
        self._do_test_start(coordination_active=True)

    def test_start_coordinated_high_hb_interval(self):
        self._do_test_start(coordination_active=True, test_interval=10,
                            coordination_heartbeat=5)

    def test_evaluation_cycle(self):
        alarm = mock.Mock(type='threshold')
        self.api_client.alarms.list.return_value = [alarm]
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            p_coord_mock = self.svc.partition_coordinator
            p_coord_mock.extract_my_subset.return_value = [alarm]

            self.svc._evaluate_assigned_alarms()

            p_coord_mock.extract_my_subset.assert_called_once_with(
                self.svc.PARTITIONING_GROUP_NAME, [alarm])
            self.threshold_eval.evaluate.assert_called_once_with(alarm)

    def test_unknown_extension_skipped(self):
        alarms = [
            mock.Mock(type='not_existing_type'),
            mock.Mock(type='threshold')
        ]

        self.api_client.alarms.list.return_value = alarms
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.svc.start()
            self.svc._evaluate_assigned_alarms()
            self.threshold_eval.evaluate.assert_called_once_with(alarms[1])

    def test_singleton_endpoint_types(self):
        endpoint_types = ["internalURL", "publicURL"]
        for endpoint_type in endpoint_types:
            self.CONF.set_override('os_endpoint_type',
                                   endpoint_type,
                                   group='service_credentials')
            with mock.patch('ceilometerclient.client.get_client') as client:
                self.svc.api_client = None
                self.svc._evaluate_assigned_alarms()
                conf = self.CONF.service_credentials
                expected = [mock.call(2,
                                      os_auth_url=conf.os_auth_url,
                                      os_region_name=conf.os_region_name,
                                      os_tenant_name=conf.os_tenant_name,
                                      os_password=conf.os_password,
                                      os_username=conf.os_username,
                                      os_cacert=conf.os_cacert,
                                      os_endpoint_type=conf.os_endpoint_type,
                                      insecure=conf.insecure)]
                actual = client.call_args_list
                self.assertEqual(expected, actual)
