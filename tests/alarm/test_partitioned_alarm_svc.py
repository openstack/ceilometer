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
"""Tests for ceilometer.alarm.service.PartitionedAlarmService.
"""
import mock
from contextlib import nested
from stevedore import extension
from stevedore.tests import manager as extension_tests

from oslo.config import cfg

from ceilometer.alarm import service
from ceilometer.tests import base


class TestPartitionedAlarmService(base.TestCase):
    def setUp(self):
        super(TestPartitionedAlarmService, self).setUp()
        self.threshold_eval = mock.Mock()
        self.api_client = mock.MagicMock()
        cfg.CONF.set_override('host',
                              'fake_host')
        cfg.CONF.set_override('partition_rpc_topic',
                              'fake_topic',
                              group='alarm')
        self.partitioned = service.PartitionedAlarmService()
        self.partitioned.tg = mock.Mock()
        self.partitioned.partition_coordinator = mock.Mock()
        self.extension_mgr = extension_tests.TestExtensionManager(
            [
                extension.Extension(
                    'threshold',
                    None,
                    None,
                    self.threshold_eval, ),
            ])
        self.partitioned.extension_manager = self.extension_mgr

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_start(self):
        test_interval = 120
        cfg.CONF.set_override('evaluation_interval',
                              test_interval,
                              group='alarm')
        get_client = 'ceilometerclient.client.get_client'
        create_conn = 'ceilometer.openstack.common.rpc.create_connection'
        with nested(mock.patch(get_client, return_value=self.api_client),
                    mock.patch(create_conn)):
            self.partitioned.start()
            pc = self.partitioned.partition_coordinator
            expected = [
                mock.call(test_interval / 4,
                          pc.report_presence,
                          0),
                mock.call(test_interval / 2,
                          pc.check_mastership,
                          test_interval,
                          test_interval,
                          self.api_client),
                mock.call(test_interval,
                          self.partitioned._evaluate_assigned_alarms,
                          test_interval),
                mock.call(604800, mock.ANY),
            ]
            actual = self.partitioned.tg.add_timer.call_args_list
            self.assertEqual(actual, expected)

    def test_presence_reporting(self):
        priority = 42
        self.partitioned.presence(mock.Mock(),
                                  dict(uuid='uuid', priority=priority))
        pc = self.partitioned.partition_coordinator
        pc.presence.assert_called_once_with('uuid', priority)

    def test_alarm_assignment(self):
        alarms = [mock.Mock()]
        self.partitioned.assign(mock.Mock(),
                                dict(uuid='uuid', alarms=alarms))
        pc = self.partitioned.partition_coordinator
        pc.assign.assert_called_once_with('uuid', alarms)

    def test_alarm_allocation(self):
        alarms = [mock.Mock()]
        self.partitioned.allocate(mock.Mock(),
                                  dict(uuid='uuid', alarms=alarms))
        pc = self.partitioned.partition_coordinator
        pc.allocate.assert_called_once_with('uuid', alarms)
