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

from oslo.config import cfg

from ceilometer.alarm import rpc as rpc_alarm
from ceilometer.openstack.common import rpc
from ceilometer.storage.models import Alarm as AlarmModel
from ceilometer.tests import base
from ceilometerclient.v2.alarms import Alarm as AlarmClient


class TestRPCAlarmNotifier(base.TestCase):
    def faux_cast(self, context, topic, msg):
        self.notified.append((topic, msg))

    def setUp(self):
        super(TestRPCAlarmNotifier, self).setUp()
        self.notified = []
        self.stubs.Set(rpc, 'cast', self.faux_cast)
        self.notifier = rpc_alarm.RPCAlarmNotifier()
        self.alarms = [
            AlarmClient(None, info={
                'name': 'instance_running_hot',
                'counter_name': 'cpu_util',
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
            AlarmClient(None, info={
                'name': 'group_running_idle',
                'counter_name': 'cpu_util',
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
            self.notifier.notify(a, previous[i], "what? %d" % i)
        self.assertEqual(len(self.notified), 2)
        for i, a in enumerate(self.alarms):
            actions = getattr(a, AlarmModel.ALARM_ACTIONS_MAP[a.state])
            self.assertEqual(self.notified[i][0],
                             cfg.CONF.alarm.notifier_rpc_topic)
            self.assertEqual(self.notified[i][1]["args"]["data"]["alarm"],
                             self.alarms[i].alarm_id)
            self.assertEqual(self.notified[i][1]["args"]["data"]["actions"],
                             actions)
            self.assertEqual(self.notified[i][1]["args"]["data"]["previous"],
                             previous[i])
            self.assertEqual(self.notified[i][1]["args"]["data"]["current"],
                             self.alarms[i].state)
            self.assertEqual(self.notified[i][1]["args"]["data"]["reason"],
                             "what? %d" % i)
