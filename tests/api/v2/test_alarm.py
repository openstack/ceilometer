# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
#
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
#         Angus Salkeld <asalkeld@redhat.com>
#
# Licensed under the Apache License, Version 2.0 (the 'License'); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
'''Tests alarm operation
'''

import logging
import uuid

from .base import FunctionalTest

from ceilometer.storage.models import Alarm

LOG = logging.getLogger(__name__)


class TestListEmptyAlarms(FunctionalTest):

    def test_empty(self):
        data = self.get_json('/alarms')
        self.assertEquals([], data)


class TestAlarms(FunctionalTest):

    def setUp(self):
        super(TestAlarms, self).setUp()

        self.auth_headers = {'X-User-Id': str(uuid.uuid1()),
                             'X-Project-Id': str(uuid.uuid1())}

        for alarm in [Alarm(alarm_id='1', name='name1',
                            counter_name='meter.test',
                            comparison_operator='gt', threshold=2.0,
                            statistic='avg',
                            user_id=self.auth_headers['X-User-Id'],
                            project_id=self.auth_headers['X-Project-Id']),
                      Alarm(alarm_id='2', name='name2',
                            counter_name='meter.mine',
                            comparison_operator='gt', threshold=2.0,
                            statistic='avg',
                            user_id=self.auth_headers['X-User-Id'],
                            project_id=self.auth_headers['X-Project-Id']),
                      Alarm(alarm_id='3', name='name3',
                            counter_name='meter.test',
                            comparison_operator='gt', threshold=2.0,
                            statistic='avg',
                            user_id=self.auth_headers['X-User-Id'],
                            project_id=self.auth_headers['X-Project-Id']),
                      ]:
            self.conn.update_alarm(alarm)

    def test_list_alarms(self):
        data = self.get_json('/alarms')
        self.assertEquals(3, len(data))
        self.assertEquals(set(r['name'] for r in data),
                          set(['name1',
                               'name2',
                               'name3']))
        self.assertEquals(set(r['counter_name'] for r in data),
                          set(['meter.test',
                               'meter.mine']))

    def test_get_alarm(self):
        data = self.get_json('/alarms/1')
        self.assertEquals(data['name'], 'name1')
        self.assertEquals(data['counter_name'], 'meter.test')

    def test_post_invalid_alarm(self):
        json = {
            'name': 'added_alarm',
            'counter_name': 'ameter',
            'comparison_operator': 'gt',
            'threshold': 2.0,
            'statistic': 'magic',
        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEquals(3, len(alarms))

    def test_post_alarm(self):
        json = {
            'name': 'added_alarm',
            'counter_name': 'ameter',
            'comparison_operator': 'gt',
            'threshold': 2.0,
            'statistic': 'avg',
        }
        self.post_json('/alarms', params=json, status=200,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEquals(4, len(alarms))

    def test_put_alarm(self):
        json = {
            'name': 'renamed_alarm',
        }
        self.put_json('/alarms/1', params=json,
                      headers=self.auth_headers)
        alarm = list(self.conn.get_alarms(alarm_id='1'))[0]
        self.assertEquals(alarm.name, json['name'])

    def test_put_alarm_wrong_field(self):
        '''
        Note: wsme will ignore unknown fields so will
        just not appear in the Alarm.
        '''
        json = {
            'name': 'renamed_alarm',
            'this_can_not_be_correct': 'ha',
        }
        resp = self.put_json('/alarms/1', params=json,
                             expect_errors=True,
                             headers=self.auth_headers)
        self.assertEquals(resp.status_code, 200)

    def test_delete_alarm(self):
        data = self.get_json('/alarms')
        self.assertEquals(3, len(data))

        self.delete('/alarms/1', status=200)
        alarms = list(self.conn.get_alarms())
        self.assertEquals(2, len(alarms))
