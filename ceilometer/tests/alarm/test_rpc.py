#
# Copyright 2013-2014 eNovance <licensing@enovance.com>
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
import eventlet
from oslo.config import fixture as fixture_config
from oslo.utils import timeutils
import six

from ceilometer.alarm import rpc as rpc_alarm
from ceilometer.alarm.storage import models
from ceilometer import messaging
from ceilometer.tests import base as tests_base


class FakeNotifier(object):
    def __init__(self, transport):
        self.rpc = messaging.get_rpc_server(
            transport, "alarm_notifier", self)
        self.notified = []

    def start(self, expected_length):
        self.expected_length = expected_length
        self.rpc.start()

    def notify_alarm(self, context, data):
        self.notified.append(data)
        if len(self.notified) == self.expected_length:
            self.rpc.stop()


class TestRPCAlarmNotifier(tests_base.BaseTestCase):
    def setUp(self):
        super(TestRPCAlarmNotifier, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.setup_messaging(self.CONF)

        self.notifier_server = FakeNotifier(self.transport)
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

    def test_rpc_target(self):
        topic = self.notifier.client.target.topic
        self.assertEqual('alarm_notifier', topic)

    def test_notify_alarm(self):
        self.notifier_server.start(2)

        previous = ['alarm', 'ok']
        for i, a in enumerate(self.alarms):
            self.notifier.notify(a, previous[i], "what? %d" % i,
                                 {'fire': '%d' % i})

        self.notifier_server.rpc.wait()

        self.assertEqual(2, len(self.notifier_server.notified))
        for i, a in enumerate(self.alarms):
            actions = getattr(a, models.Alarm.ALARM_ACTIONS_MAP[a.state])
            self.assertEqual(self.alarms[i].alarm_id,
                             self.notifier_server.notified[i]["alarm_id"])
            self.assertEqual(actions,
                             self.notifier_server.notified[i]["actions"])
            self.assertEqual(previous[i],
                             self.notifier_server.notified[i]["previous"])
            self.assertEqual(self.alarms[i].state,
                             self.notifier_server.notified[i]["current"])
            self.assertEqual("what? %d" % i,
                             self.notifier_server.notified[i]["reason"])
            self.assertEqual({'fire': '%d' % i},
                             self.notifier_server.notified[i]["reason_data"])

    def test_notify_non_string_reason(self):
        self.notifier_server.start(1)
        self.notifier.notify(self.alarms[0], 'ok', 42, {})
        self.notifier_server.rpc.wait()
        reason = self.notifier_server.notified[0]['reason']
        self.assertIsInstance(reason, six.string_types)

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
        self.assertEqual(0, len(self.notifier_server.notified))


class FakeCoordinator(object):
    def __init__(self, transport):
        self.rpc = messaging.get_rpc_server(
            transport, "alarm_partition_coordination", self)
        self.notified = []

    def presence(self, context, data):
        self._record('presence', data)

    def allocate(self, context, data):
        self._record('allocate', data)

    def assign(self, context, data):
        self._record('assign', data)

    def _record(self, method, data):
        self.notified.append((method, data))
        self.rpc.stop()


class TestRPCAlarmPartitionCoordination(tests_base.BaseTestCase):
    def setUp(self):
        super(TestRPCAlarmPartitionCoordination, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.setup_messaging(self.CONF)

        self.coordinator_server = FakeCoordinator(self.transport)
        self.coordinator_server.rpc.start()
        eventlet.sleep()  # must be sure that fanout queue is created

        self.coordination = rpc_alarm.RPCAlarmPartitionCoordination()
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

    def test_coordination_presence(self):
        id = str(uuid.uuid4())
        priority = float(timeutils.utcnow().strftime('%s.%f'))
        self.coordination.presence(id, priority)
        self.coordinator_server.rpc.wait()
        method, args = self.coordinator_server.notified[0]
        self.assertEqual(id, args['uuid'])
        self.assertEqual(priority, args['priority'])
        self.assertEqual('presence', method)

    def test_coordination_assign(self):
        id = str(uuid.uuid4())
        self.coordination.assign(id, self.alarms)
        self.coordinator_server.rpc.wait()
        method, args = self.coordinator_server.notified[0]
        self.assertEqual(id, args['uuid'])
        self.assertEqual(2, len(args['alarms']))
        self.assertEqual('assign', method)

    def test_coordination_allocate(self):
        id = str(uuid.uuid4())
        self.coordination.allocate(id, self.alarms)
        self.coordinator_server.rpc.wait()
        method, args = self.coordinator_server.notified[0]
        self.assertEqual(id, args['uuid'])
        self.assertEqual(2, len(args['alarms']))
        self.assertEqual('allocate', method)
