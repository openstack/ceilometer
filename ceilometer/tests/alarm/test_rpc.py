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

import uuid

from ceilometerclient.v2 import alarms
import mock

from ceilometer.alarm import rpc as rpc_alarm
from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common.fixture import mockpatch
from ceilometer.openstack.common import rpc
from ceilometer.openstack.common import test
from ceilometer.openstack.common import timeutils
from ceilometer.storage import models


class TestRPCAlarmNotifier(test.BaseTestCase):
    def fake_cast(self, context, topic, msg):
        self.notified.append((topic, msg))
        self.CONF = self.useFixture(config.Config()).conf

    def setUp(self):
        super(TestRPCAlarmNotifier, self).setUp()
        self.notified = []
        self.useFixture(mockpatch.PatchObject(
            rpc, 'cast',
            side_effect=self.fake_cast))
        self.notifier = rpc_alarm.RPCAlarmNotifier()
        self.alarms = [
            alarms.Alarm(None, info={
                'name': 'instance_running_hot',
                'meter_name': 'cpu_util',
                'comparison_operator': 'gt',
                'threshold': 80.0,
                'evaluation_periods': 5,
                'statistic': 'avg',
                'state': 'ok',
                'ok_actions': ['http://host:8080/path'],
                'user_id': 'foobar',
                'project_id': 'snafu',
                'period': 60,
                'alarm_id': str(uuid.uuid4()),
                'matching_metadata':{'resource_id':
                                     'my_instance'}
            }),
            alarms.Alarm(None, info={
                'name': 'group_running_idle',
                'meter_name': 'cpu_util',
                'comparison_operator': 'le',
                'threshold': 10.0,
                'statistic': 'max',
                'evaluation_periods': 4,
                'state': 'insufficient data',
                'insufficient_data_actions': ['http://other_host/path'],
                'user_id': 'foobar',
                'project_id': 'snafu',
                'period': 300,
                'alarm_id': str(uuid.uuid4()),
                'matching_metadata':{'metadata.user_metadata.AS':
                                     'my_group'}
            }),
        ]

    def test_notify_alarm(self):
        previous = ['alarm', 'ok']
        for i, a in enumerate(self.alarms):
            self.notifier.notify(a, previous[i], "what? %d" % i,
                                 {'fire': '%d' % i})
        self.assertEqual(2, len(self.notified))
        for i, a in enumerate(self.alarms):
            actions = getattr(a, models.Alarm.ALARM_ACTIONS_MAP[a.state])
            self.assertEqual(self.CONF.alarm.notifier_rpc_topic,
                             self.notified[i][0])
            self.assertEqual(self.alarms[i].alarm_id,
                             self.notified[i][1]["args"]["data"]["alarm_id"])
            self.assertEqual(actions,
                             self.notified[i][1]["args"]["data"]["actions"])
            self.assertEqual(previous[i],
                             self.notified[i][1]["args"]["data"]["previous"])
            self.assertEqual(self.alarms[i].state,
                             self.notified[i][1]["args"]["data"]["current"])
            self.assertEqual("what? %d" % i,
                             self.notified[i][1]["args"]["data"]["reason"])
            self.assertEqual(
                {'fire': '%d' % i},
                self.notified[i][1]["args"]["data"]["reason_data"])

    def test_notify_non_string_reason(self):
        self.notifier.notify(self.alarms[0], 'ok', 42, {})
        reason = self.notified[0][1]['args']['data']['reason']
        self.assertIsInstance(reason, basestring)

    def test_notify_no_actions(self):
        alarm = alarms.Alarm(None, info={
            'name': 'instance_running_hot',
            'meter_name': 'cpu_util',
            'comparison_operator': 'gt',
            'threshold': 80.0,
            'evaluation_periods': 5,
            'statistic': 'avg',
            'state': 'ok',
            'user_id': 'foobar',
            'project_id': 'snafu',
            'period': 60,
            'ok_actions': [],
            'alarm_id': str(uuid.uuid4()),
            'matching_metadata': {'resource_id':
                                  'my_instance'}
        })
        self.notifier.notify(alarm, 'alarm', "what?", {})
        self.assertEqual(0, len(self.notified))


class TestRPCAlarmPartitionCoordination(test.BaseTestCase):
    def fake_fanout_cast(self, context, topic, msg):
        self.notified.append((topic, msg))

    def setUp(self):
        super(TestRPCAlarmPartitionCoordination, self).setUp()
        self.notified = []
        self.useFixture(mockpatch.PatchObject(
            rpc, 'fanout_cast',
            side_effect=self.fake_fanout_cast))
        self.ordination = rpc_alarm.RPCAlarmPartitionCoordination()
        self.alarms = [mock.MagicMock(), mock.MagicMock()]

    def test_ordination_presence(self):
        id = uuid.uuid4()
        priority = float(timeutils.utcnow().strftime('%s.%f'))
        self.ordination.presence(id, priority)
        topic, msg = self.notified[0]
        self.assertEqual('alarm_partition_coordination', topic)
        self.assertEqual(id, msg['args']['data']['uuid'])
        self.assertEqual(priority, msg['args']['data']['priority'])
        self.assertEqual('presence', msg['method'])

    def test_ordination_assign(self):
        id = uuid.uuid4()
        self.ordination.assign(id, self.alarms)
        topic, msg = self.notified[0]
        self.assertEqual('alarm_partition_coordination', topic)
        self.assertEqual(id, msg['args']['data']['uuid'])
        self.assertEqual(2, len(msg['args']['data']['alarms']))
        self.assertEqual('assign', msg['method'])

    def test_ordination_allocate(self):
        id = uuid.uuid4()
        self.ordination.allocate(id, self.alarms)
        topic, msg = self.notified[0]
        self.assertEqual('alarm_partition_coordination', topic)
        self.assertEqual(id, msg['args']['data']['uuid'])
        self.assertEqual(2, len(msg['args']['data']['alarms']))
        self.assertEqual('allocate', msg['method'])
