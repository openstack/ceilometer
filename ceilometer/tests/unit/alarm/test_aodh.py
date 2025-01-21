#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

from ceilometer.alarm import aodh
from ceilometer.polling import manager
from ceilometer import service
import ceilometer.tests.base as base

ALARM_METRIC_LIST = [
    {
        'evaluation_results': [{
            'alarm_id': 'b8e17f58-089a-43fc-a96b-e9bcac4d4b53',
            'project_id': '2dd8edd6c8c24f49bf04670534f6b357',
            'state_counters': {
                'ok': 2,
                'alarm': 5,
                'insufficient data': 0,
            }
        }, {
            'alarm_id': 'fa386719-67e3-42ff-aec8-17e547dac77a',
            'project_id': 'd45b070bcce04ca99546128a40854e7c',
            'state_counters': {
                'ok': 50,
                'alarm': 3,
                'insufficient data': 10,
            }
        }],
    },
]


class TestAlarmEvaluationResultPollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = aodh.EvaluationResultPollster(conf)

    def test_alarm_pollster(self):
        alarm_samples = list(
            self.pollster.get_samples(self.manager,
                                      {},
                                      resources=ALARM_METRIC_LIST))
        self.assertEqual(6, len(alarm_samples))
        self.assertEqual('alarm.evaluation_result', alarm_samples[0].name)
        self.assertEqual(2, alarm_samples[0].volume)
        self.assertEqual('2dd8edd6c8c24f49bf04670534f6b357',
                         alarm_samples[0].project_id)
        self.assertEqual('b8e17f58-089a-43fc-a96b-e9bcac4d4b53',
                         alarm_samples[0].resource_id)
        self.assertEqual('ok',
                         alarm_samples[0].resource_metadata['alarm_state'])
