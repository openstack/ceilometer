# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
#
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
#         Angus Salkeld <asalkeld@redhat.com>
#         Eoghan Glynn <eglynn@redhat.com>
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
'''Tests alarm operation
'''

import datetime
import json as jsonutils
import logging
import uuid
import testscenarios

from oslo.config import cfg

from .base import FunctionalTest

from ceilometer.storage.models import Alarm
from ceilometer.tests import db as tests_db

load_tests = testscenarios.load_tests_apply_scenarios

LOG = logging.getLogger(__name__)


class TestListEmptyAlarms(FunctionalTest,
                          tests_db.MixinTestsWithBackendScenarios):

    def test_empty(self):
        data = self.get_json('/alarms')
        self.assertEqual([], data)


class TestAlarms(FunctionalTest,
                 tests_db.MixinTestsWithBackendScenarios):

    def setUp(self):
        super(TestAlarms, self).setUp()

        self.auth_headers = {'X-User-Id': str(uuid.uuid4()),
                             'X-Project-Id': str(uuid.uuid4())}
        for alarm in [Alarm(name='name1',
                            alarm_id='a',
                            meter_name='meter.test',
                            comparison_operator='gt', threshold=2.0,
                            statistic='avg',
                            repeat_actions=True,
                            user_id=self.auth_headers['X-User-Id'],
                            project_id=self.auth_headers['X-Project-Id']),
                      Alarm(name='name2',
                            alarm_id='b',
                            meter_name='meter.mine',
                            comparison_operator='gt', threshold=2.0,
                            statistic='avg',
                            user_id=self.auth_headers['X-User-Id'],
                            project_id=self.auth_headers['X-Project-Id']),
                      Alarm(name='name3',
                            alarm_id='c',
                            meter_name='meter.test',
                            comparison_operator='gt', threshold=2.0,
                            statistic='avg',
                            user_id=self.auth_headers['X-User-Id'],
                            project_id=self.auth_headers['X-Project-Id'])]:
            self.conn.update_alarm(alarm)

    def test_list_alarms(self):
        data = self.get_json('/alarms')
        self.assertEqual(3, len(data))
        self.assertEqual(set(r['name'] for r in data),
                         set(['name1', 'name2', 'name3']))
        self.assertEqual(set(r['meter_name'] for r in data),
                         set(['meter.test', 'meter.mine']))

    def test_get_alarm(self):
        alarms = self.get_json('/alarms',
                               q=[{'field': 'name',
                                   'value': 'name1',
                                   }])
        for a in alarms:
            print('%s: %s' % (a['name'], a['alarm_id']))
        self.assertEqual(alarms[0]['name'], 'name1')
        self.assertEqual(alarms[0]['meter_name'], 'meter.test')

        one = self.get_json('/alarms/%s' % alarms[0]['alarm_id'])
        self.assertEqual(one['name'], 'name1')
        self.assertEqual(one['meter_name'], 'meter.test')
        self.assertEqual(one['alarm_id'], alarms[0]['alarm_id'])
        self.assertEqual(one['repeat_actions'], alarms[0]['repeat_actions'])

    def test_post_invalid_alarm(self):
        json = {
            'name': 'added_alarm',
            'meter_name': 'ameter',
            'comparison_operator': 'gt',
            'threshold': 2.0,
            'statistic': 'magic',
        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_post_alarm(self):
        json = {
            'name': 'added_alarm',
            'meter_name': 'ameter',
            'comparison_operator': 'gt',
            'threshold': 2.0,
            'statistic': 'avg',
            'repeat_actions': True,
        }
        self.post_json('/alarms', params=json, status=200,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))
        for alarm in alarms:
            if alarm.name == 'added_alarm':
                self.assertEqual(alarm.repeat_actions, True)
                break
        else:
            self.fail("Alarm not found")

    def test_put_alarm(self):
        json = {
            'name': 'renamed_alarm',
            'repeat_actions': True,
        }
        data = self.get_json('/alarms',
                             q=[{'field': 'name',
                                 'value': 'name1',
                                 }])
        self.assertEqual(1, len(data))
        alarm_id = data[0]['alarm_id']

        self.put_json('/alarms/%s' % alarm_id,
                      params=json,
                      headers=self.auth_headers)
        alarm = list(self.conn.get_alarms(alarm_id=alarm_id))[0]
        self.assertEqual(alarm.name, json['name'])
        self.assertEqual(alarm.repeat_actions, json['repeat_actions'])

    def test_put_alarm_wrong_field(self):
        # Note: wsme will ignore unknown fields so will just not appear in
        # the Alarm.
        json = {
            'name': 'renamed_alarm',
            'this_can_not_be_correct': 'ha',
        }
        data = self.get_json('/alarms',
                             q=[{'field': 'name',
                                 'value': 'name1',
                                 }],
                             headers=self.auth_headers)
        self.assertEqual(1, len(data))

        resp = self.put_json('/alarms/%s' % data[0]['alarm_id'],
                             params=json,
                             expect_errors=True,
                             headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)

    def test_delete_alarm(self):
        data = self.get_json('/alarms')
        self.assertEqual(3, len(data))

        self.delete('/alarms/%s' % data[0]['alarm_id'],
                    status=200)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(2, len(alarms))

    def _get_alarm(self, id):
        data = self.get_json('/alarms')
        match = [a for a in data if a['alarm_id'] == id]
        self.assertEqual(1, len(match), 'alarm %s not found' % id)
        return match[0]

    def _get_alarm_history(self, alarm, auth_headers=None):
        return self.get_json('/alarms/%s/history' % alarm['alarm_id'],
                             headers=auth_headers or self.auth_headers)

    def _update_alarm(self, alarm, data, auth_headers=None):
        self.put_json('/alarms/%s' % alarm['alarm_id'],
                      params=data,
                      headers=auth_headers or self.auth_headers)

    def _assert_is_subset(self, expected, actual):
        for k, v in expected.iteritems():
            self.assertEqual(v, actual.get(k), 'mismatched field: %s' % k)
        self.assertTrue(actual['event_id'] is not None)

    def _assert_in_json(self, expected, actual):
        for k, v in expected.iteritems():
            fragment = jsonutils.dumps({k: v})[1:-1]
            self.assertTrue(fragment in actual,
                            '%s not in %s' % (fragment, actual))

    def test_record_alarm_history_config(self):
        cfg.CONF.set_override('record_history', False, group='alarm')
        alarm = self._get_alarm('a')
        history = self._get_alarm_history(alarm)
        self.assertEqual([], history)
        self._update_alarm(alarm, dict(name='renamed'))
        history = self._get_alarm_history(alarm)
        self.assertEqual([], history)
        cfg.CONF.set_override('record_history', True, group='alarm')
        self._update_alarm(alarm, dict(name='foobar'))
        history = self._get_alarm_history(alarm)
        self.assertEqual(1, len(history))

    def test_get_recorded_alarm_history_on_create(self):
        new_alarm = dict(name='new_alarm',
                         meter_name='other_meter',
                         comparison_operator='le',
                         threshold=42.0,
                         statistic='max')
        self.post_json('/alarms', params=new_alarm, status=200,
                       headers=self.auth_headers)
        alarm = self.get_json('/alarms')[3]
        history = self._get_alarm_history(alarm)
        self.assertEqual(1, len(history))
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    on_behalf_of=alarm['project_id'],
                                    project_id=alarm['project_id'],
                                    type='creation',
                                    user_id=alarm['user_id']),
                               history[0])
        self._assert_in_json(new_alarm, history[0]['detail'])

    def _do_test_get_recorded_alarm_history_on_update(self,
                                                      data,
                                                      type,
                                                      detail,
                                                      auth=None):
        alarm = self._get_alarm('a')
        history = self._get_alarm_history(alarm)
        self.assertEqual([], history)
        self._update_alarm(alarm, data, auth)
        history = self._get_alarm_history(alarm)
        self.assertEqual(1, len(history))
        project_id = auth['X-Project-Id'] if auth else alarm['project_id']
        user_id = auth['X-User-Id'] if auth else alarm['user_id']
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    detail=detail,
                                    on_behalf_of=alarm['project_id'],
                                    project_id=project_id,
                                    type=type,
                                    user_id=user_id),
                               history[0])

    def test_get_recorded_alarm_history_rule_change(self):
        now = datetime.datetime.utcnow().isoformat()
        data = dict(name='renamed', timestamp=now)
        detail = '{"timestamp": "%s", "name": "renamed"}' % now
        self._do_test_get_recorded_alarm_history_on_update(data,
                                                           'rule change',
                                                           detail)

    def test_get_recorded_alarm_history_state_transition(self):
        data = dict(state='alarm')
        detail = '{"state": "alarm"}'
        self._do_test_get_recorded_alarm_history_on_update(data,
                                                           'state transition',
                                                           detail)

    def test_get_recorded_alarm_history_rule_change_on_behalf_of(self):
        data = dict(name='renamed')
        detail = '{"name": "renamed"}'
        auth = {'X-Roles': 'admin',
                'X-User-Id': str(uuid.uuid4()),
                'X-Project-Id': str(uuid.uuid4())}
        self._do_test_get_recorded_alarm_history_on_update(data,
                                                           'rule change',
                                                           detail,
                                                           auth)

    def test_get_recorded_alarm_history_segregation(self):
        data = dict(name='renamed')
        detail = '{"name": "renamed"}'
        self._do_test_get_recorded_alarm_history_on_update(data,
                                                           'rule change',
                                                           detail)
        auth = {'X-Roles': 'member',
                'X-User-Id': str(uuid.uuid4()),
                'X-Project-Id': str(uuid.uuid4())}
        history = self._get_alarm_history(self._get_alarm('a'), auth)
        self.assertEqual([], history)

    def test_get_recorded_alarm_history_preserved_after_deletion(self):
        alarm = self._get_alarm('a')
        history = self._get_alarm_history(alarm)
        self.assertEqual([], history)
        self._update_alarm(alarm, dict(name='renamed'))
        history = self._get_alarm_history(alarm)
        self.assertEqual(1, len(history))
        alarm = self._get_alarm('a')
        self.delete('/alarms/%s' % alarm['alarm_id'],
                    headers=self.auth_headers,
                    status=200)
        history = self._get_alarm_history(alarm)
        self.assertEqual(2, len(history))
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    on_behalf_of=alarm['project_id'],
                                    project_id=alarm['project_id'],
                                    type='deletion',
                                    user_id=alarm['user_id']),
                               history[0])
        self._assert_in_json(alarm, history[0]['detail'])

    def test_get_nonexistent_alarm_history(self):
        # the existence of alarm history is independent of the
        # continued existence of the alarm itself
        history = self._get_alarm_history(dict(alarm_id='foobar'))
        self.assertEqual([], history)
