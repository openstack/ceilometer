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

import mock

from six import moves
import testscenarios

from ceilometer.storage import models
from ceilometer.tests.api.v2 import FunctionalTest
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
        for alarm in [
            models.Alarm(name='name1',
                         type='threshold',
                         enabled=True,
                         alarm_id='a',
                         description='a',
                         state='insufficient data',
                         state_timestamp=None,
                         timestamp=None,
                         ok_actions=[],
                         insufficient_data_actions=[],
                         alarm_actions=[],
                         repeat_actions=True,
                         user_id=self.auth_headers['X-User-Id'],
                         project_id=self.auth_headers['X-Project-Id'],
                         time_constraints=[dict(name='testcons',
                                                start='0 11 * * *',
                                                duration=300)],
                         rule=dict(comparison_operator='gt',
                                   threshold=2.0,
                                   statistic='avg',
                                   evaluation_periods=60,
                                   period=1,
                                   meter_name='meter.test',
                                   query=[{'field': 'project_id',
                                           'op': 'eq', 'value':
                                           self.auth_headers['X-Project-Id']}
                                          ])
                         ),
            models.Alarm(name='name2',
                         type='threshold',
                         enabled=True,
                         alarm_id='b',
                         description='b',
                         state='insufficient data',
                         state_timestamp=None,
                         timestamp=None,
                         ok_actions=[],
                         insufficient_data_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         user_id=self.auth_headers['X-User-Id'],
                         project_id=self.auth_headers['X-Project-Id'],
                         time_constraints=[],
                         rule=dict(comparison_operator='gt',
                                   threshold=4.0,
                                   statistic='avg',
                                   evaluation_periods=60,
                                   period=1,
                                   meter_name='meter.test',
                                   query=[{'field': 'project_id',
                                           'op': 'eq', 'value':
                                           self.auth_headers['X-Project-Id']}
                                          ])
                         ),
            models.Alarm(name='name3',
                         type='threshold',
                         enabled=True,
                         alarm_id='c',
                         description='c',
                         state='insufficient data',
                         state_timestamp=None,
                         timestamp=None,
                         ok_actions=[],
                         insufficient_data_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         user_id=self.auth_headers['X-User-Id'],
                         project_id=self.auth_headers['X-Project-Id'],
                         time_constraints=[],
                         rule=dict(comparison_operator='gt',
                                   threshold=3.0,
                                   statistic='avg',
                                   evaluation_periods=60,
                                   period=1,
                                   meter_name='meter.mine',
                                   query=[{'field': 'project_id',
                                           'op': 'eq', 'value':
                                           self.auth_headers['X-Project-Id']}
                                          ])
                         ),
            models.Alarm(name='name4',
                         type='combination',
                         enabled=True,
                         alarm_id='d',
                         description='d',
                         state='insufficient data',
                         state_timestamp=None,
                         timestamp=None,
                         ok_actions=[],
                         insufficient_data_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         user_id=self.auth_headers['X-User-Id'],
                         project_id=self.auth_headers['X-Project-Id'],
                         time_constraints=[],
                         rule=dict(alarm_ids=['a', 'b'],
                                   operator='or')
                         )]:
            self.conn.update_alarm(alarm)

    @staticmethod
    def _add_default_threshold_rule(alarm):
        if 'exclude_outliers' not in alarm['threshold_rule']:
            alarm['threshold_rule']['exclude_outliers'] = False

    def _verify_alarm(self, json, alarm, expected_name=None):
        if expected_name and alarm.name != expected_name:
            self.fail("Alarm not found")
        self._add_default_threshold_rule(json)
        for key in json:
            if key.endswith('_rule'):
                storage_key = 'rule'
            else:
                storage_key = key
            self.assertEqual(json[key], getattr(alarm, storage_key))

    def test_list_alarms(self):
        data = self.get_json('/alarms')
        self.assertEqual(4, len(data))
        self.assertEqual(set(['name1', 'name2', 'name3', 'name4']),
                         set(r['name'] for r in data))
        self.assertEqual(set(['meter.test', 'meter.mine']),
                         set(r['threshold_rule']['meter_name']
                             for r in data if 'threshold_rule' in r))
        self.assertEqual(set(['or']),
                         set(r['combination_rule']['operator']
                             for r in data if 'combination_rule' in r))

    def test_alarms_query_with_timestamp(self):
        date_time = datetime.datetime(2012, 7, 2, 10, 41)
        isotime = date_time.isoformat()
        resp = self.get_json('/alarms',
                             q=[{'field': 'timestamp',
                                 'op': 'gt',
                                 'value': isotime}],
                             expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(jsonutils.loads(resp.body)['error_message']
                         ['faultstring'],
                         'Unknown argument: "timestamp": '
                         'not valid for this resource')

    def test_get_not_existing_alarm(self):
        resp = self.get_json('/alarms/alarm-id-3', expect_errors=True)
        self.assertEqual(404, resp.status_code)
        self.assertEqual("Alarm alarm-id-3 Not Found",
                         jsonutils.loads(resp.body)['error_message']
                         ['faultstring'])

    def test_get_alarm(self):
        alarms = self.get_json('/alarms',
                               q=[{'field': 'name',
                                   'value': 'name1',
                                   }])
        self.assertEqual('name1', alarms[0]['name'])
        self.assertEqual('meter.test',
                         alarms[0]['threshold_rule']['meter_name'])

        one = self.get_json('/alarms/%s' % alarms[0]['alarm_id'])
        self.assertEqual('name1', one['name'])
        self.assertEqual('meter.test', one['threshold_rule']['meter_name'])
        self.assertEqual(alarms[0]['alarm_id'], one['alarm_id'])
        self.assertEqual(alarms[0]['repeat_actions'], one['repeat_actions'])
        self.assertEqual(alarms[0]['time_constraints'],
                         one['time_constraints'])

    def test_get_alarm_disabled(self):
        alarm = models.Alarm(name='disabled',
                             type='combination',
                             enabled=False,
                             alarm_id='d',
                             description='d',
                             state='insufficient data',
                             state_timestamp=None,
                             timestamp=None,
                             ok_actions=[],
                             insufficient_data_actions=[],
                             alarm_actions=[],
                             repeat_actions=False,
                             user_id=self.auth_headers['X-User-Id'],
                             project_id=self.auth_headers['X-Project-Id'],
                             time_constraints=[],
                             rule=dict(alarm_ids=['a', 'b'], operator='or'))
        self.conn.update_alarm(alarm)

        alarms = self.get_json('/alarms',
                               q=[{'field': 'enabled',
                                   'value': 'False'}])
        self.assertEqual(1, len(alarms))
        self.assertEqual('disabled', alarms[0]['name'])

        one = self.get_json('/alarms/%s' % alarms[0]['alarm_id'])
        self.assertEqual('disabled', one['name'])

    def test_get_alarm_combination(self):
        alarms = self.get_json('/alarms',
                               q=[{'field': 'name',
                                   'value': 'name4',
                                   }])
        self.assertEqual('name4', alarms[0]['name'])
        self.assertEqual(['a', 'b'],
                         alarms[0]['combination_rule']['alarm_ids'])
        self.assertEqual('or', alarms[0]['combination_rule']['operator'])

        one = self.get_json('/alarms/%s' % alarms[0]['alarm_id'])
        self.assertEqual('name4', one['name'])
        self.assertEqual(['a', 'b'],
                         alarms[0]['combination_rule']['alarm_ids'])
        self.assertEqual('or', alarms[0]['combination_rule']['operator'])
        self.assertEqual(alarms[0]['alarm_id'], one['alarm_id'])
        self.assertEqual(alarms[0]['repeat_actions'], one['repeat_actions'])

    def test_post_alarm_wsme_workaround(self):
        jsons = {
            'type': {
                'name': 'missing type',
                'threshold_rule': {
                    'meter_name': 'ameter',
                    'threshold': 2.0,
                }
            },
            'name': {
                'type': 'threshold',
                'threshold_rule': {
                    'meter_name': 'ameter',
                    'threshold': 2.0,
                }
            },
            'threshold_rule/meter_name': {
                'name': 'missing meter_name',
                'type': 'threshold',
                'threshold_rule': {
                    'threshold': 2.0,
                }
            },
            'threshold_rule/threshold': {
                'name': 'missing threshold',
                'type': 'threshold',
                'threshold_rule': {
                    'meter_name': 'ameter',
                }
            },
            'combination_rule/alarm_ids': {
                'name': 'missing alarm_ids',
                'type': 'combination',
                'combination_rule': {}
            }
        }
        for field, json in jsons.iteritems():
            resp = self.post_json('/alarms', params=json, expect_errors=True,
                                  status=400, headers=self.auth_headers)
            self.assertEqual("Invalid input for field/attribute %s."
                             " Value: \'None\'. Mandatory field missing."
                             % field.split('/', 1)[-1],
                             resp.json['error_message']['faultstring'])
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))

    def test_post_invalid_alarm_time_constraint_start(self):
        json = {
            'name': 'added_alarm_invalid_constraint_duration',
            'type': 'threshold',
            'time_constraints': [
                {
                    'name': 'testcons',
                    'start': '11:00am',
                    'duration': 10
                }
            ],
            'threshold_rule': {
                'meter_name': 'ameter',
                'threshold': 300.0
            }
        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))

    def test_post_duplicate_time_constraint_name(self):
        json = {
            'name': 'added_alarm_duplicate_constraint_name',
            'type': 'threshold',
            'time_constraints': [
                {
                    'name': 'testcons',
                    'start': '* 11 * * *',
                    'duration': 10
                },
                {
                    'name': 'testcons',
                    'start': '* * * * *',
                    'duration': 20
                }
            ],
            'threshold_rule': {
                'meter_name': 'ameter',
                'threshold': 300.0
            }
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        self.assertEqual(
            "Time constraint names must be unique for a given alarm.",
            resp.json['error_message']['faultstring'])
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))

    def test_post_invalid_alarm_time_constraint_duration(self):
        json = {
            'name': 'added_alarm_invalid_constraint_duration',
            'type': 'threshold',
            'time_constraints': [
                {
                    'name': 'testcons',
                    'start': '* 11 * * *',
                    'duration': -1,
                }
            ],
            'threshold_rule': {
                'meter_name': 'ameter',
                'threshold': 300.0
            }
        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))

    def test_post_invalid_alarm_time_constraint_timezone(self):
        json = {
            'name': 'added_alarm_invalid_constraint_timezone',
            'type': 'threshold',
            'time_constraints': [
                {
                    'name': 'testcons',
                    'start': '* 11 * * *',
                    'duration': 10,
                    'timezone': 'aaaa'
                }
            ],
            'threshold_rule': {
                'meter_name': 'ameter',
                'threshold': 300.0
            }
        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))

    def test_post_invalid_alarm_period(self):
        json = {
            'name': 'added_alarm_invalid_period',
            'type': 'threshold',
            'threshold_rule': {
                'meter_name': 'ameter',
                'comparison_operator': 'gt',
                'threshold': 2.0,
                'statistic': 'avg',
                'period': -1,
            }

        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))

    def test_post_null_threshold_rule(self):
        json = {
            'name': 'added_alarm_invalid_threshold_rule',
            'type': 'threshold',
            'threshold_rule': None,
            'combination_rule': None,
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        self.assertEqual(
            "threshold_rule must be set for threshold type alarm",
            resp.json['error_message']['faultstring'])

    def test_post_invalid_alarm_statistic(self):
        json = {
            'name': 'added_alarm',
            'type': 'threshold',
            'threshold_rule': {
                'meter_name': 'ameter',
                'comparison_operator': 'gt',
                'threshold': 2.0,
                'statistic': 'magic',
            }
        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))

    def test_post_invalid_alarm_query(self):
        json = {
            'name': 'added_alarm',
            'type': 'threshold',
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.invalid',
                           'field': 'gt',
                           'value': 'value'}],
                'comparison_operator': 'gt',
                'threshold': 2.0,
                'statistic': 'avg',
            }
        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))

    def test_post_invalid_alarm_query_field_type(self):
        json = {
            'name': 'added_alarm',
            'type': 'threshold',
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.valid',
                           'op': 'eq',
                           'value': 'value',
                           'type': 'blob'}],
                'comparison_operator': 'gt',
                'threshold': 2.0,
                'statistic': 'avg',
            }
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        expected_error_message = 'The data type blob is not supported.'
        resp_string = jsonutils.loads(resp.body)
        fault_string = resp_string['error_message']['faultstring']
        self.assertTrue(fault_string.startswith(expected_error_message))
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))

    def test_post_invalid_alarm_have_multiple_rules(self):
        json = {
            'name': 'added_alarm',
            'type': 'threshold',
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'meter',
                           'value': 'ameter'}],
                'comparison_operator': 'gt',
                'threshold': 2.0,
            },
            'combination_rule': {
                'alarm_ids': ['a', 'b'],

            }
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))
        self.assertEqual('threshold_rule and combination_rule cannot '
                         'be set at the same time',
                         resp.json['error_message']['faultstring'])

    def test_post_invalid_alarm_timestamp_in_threshold_rule(self):
        date_time = datetime.datetime(2012, 7, 2, 10, 41)
        isotime = date_time.isoformat()

        json = {
            'name': 'invalid_alarm',
            'type': 'threshold',
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'timestamp',
                           'op': 'gt',
                           'value': isotime}],
                'comparison_operator': 'gt',
                'threshold': 2.0,
            }
        }
        resp = self.post_json('/alarms', params=json, expect_errors=True,
                              status=400, headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))
        self.assertEqual(
            'Unknown argument: "timestamp": '
            'not valid for this resource',
            resp.json['error_message']['faultstring'])

    def test_post_alarm_defaults(self):
        to_check = {
            'enabled': True,
            'name': 'added_alarm_defaults',
            'state': 'insufficient data',
            'description': ('Alarm when ameter is eq a avg of '
                            '300.0 over 60 seconds'),
            'type': 'threshold',
            'ok_actions': [],
            'alarm_actions': [],
            'insufficient_data_actions': [],
            'repeat_actions': False,
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'project_id',
                           'op': 'eq',
                           'value': self.auth_headers['X-Project-Id']}],
                'threshold': 300.0,
                'comparison_operator': 'eq',
                'statistic': 'avg',
                'evaluation_periods': 1,
                'period': 60,
            }

        }
        self._add_default_threshold_rule(to_check)

        json = {
            'name': 'added_alarm_defaults',
            'type': 'threshold',
            'threshold_rule': {
                'meter_name': 'ameter',
                'threshold': 300.0
            }
        }
        self.post_json('/alarms', params=json, status=201,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(5, len(alarms))
        for alarm in alarms:
            if alarm.name == 'added_alarm_defaults':
                for key in to_check:
                    if key.endswith('_rule'):
                        storage_key = 'rule'
                    else:
                        storage_key = key
                    self.assertEqual(to_check[key],
                                     getattr(alarm, storage_key))
                break
        else:
            self.fail("Alarm not found")

    def test_post_conflict(self):
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'threshold',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.field',
                           'op': 'eq',
                           'value': '5',
                           'type': 'string'}],
                'comparison_operator': 'le',
                'statistic': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'period': '180',
            }
        }

        self.post_json('/alarms', params=json, status=201,
                       headers=self.auth_headers)
        self.post_json('/alarms', params=json, status=409,
                       headers=self.auth_headers)

    def _do_test_post_alarm(self, exclude_outliers=None):
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'threshold',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.field',
                           'op': 'eq',
                           'value': '5',
                           'type': 'string'}],
                'comparison_operator': 'le',
                'statistic': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'period': '180',
            }
        }
        if exclude_outliers is not None:
            json['threshold_rule']['exclude_outliers'] = exclude_outliers

        self.post_json('/alarms', params=json, status=201,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))
        json['threshold_rule']['query'].append({
            'field': 'project_id', 'op': 'eq',
            'value': self.auth_headers['X-Project-Id']})
        # to check to IntegerType type conversion
        json['threshold_rule']['evaluation_periods'] = 3
        json['threshold_rule']['period'] = 180
        self._verify_alarm(json, alarms[0], 'added_alarm')

    def test_post_alarm_outlier_exclusion_set(self):
        self._do_test_post_alarm(True)

    def test_post_alarm_outlier_exclusion_clear(self):
        self._do_test_post_alarm(False)

    def test_post_alarm_outlier_exclusion_defaulted(self):
        self._do_test_post_alarm()

    def test_post_alarm_noauth(self):
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'threshold',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.field',
                           'op': 'eq',
                           'value': '5',
                           'type': 'string'}],
                'comparison_operator': 'le',
                'statistic': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'exclude_outliers': False,
                'period': '180',
            }
        }
        self.post_json('/alarms', params=json, status=201)
        alarms = list(self.conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))
        # to check to BoundedInt type conversion
        json['threshold_rule']['evaluation_periods'] = 3
        json['threshold_rule']['period'] = 180
        if alarms[0].name == 'added_alarm':
            for key in json:
                if key.endswith('_rule'):
                    storage_key = 'rule'
                else:
                    storage_key = key
                self.assertEqual(getattr(alarms[0], storage_key),
                                 json[key])
        else:
            self.fail("Alarm not found")

    def _do_test_post_alarm_as_admin(self, explicit_project_constraint):
        """Test the creation of an alarm as admin for another project."""
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'threshold',
            'user_id': 'auseridthatisnotmine',
            'project_id': 'aprojectidthatisnotmine',
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.field',
                           'op': 'eq',
                           'value': '5',
                           'type': 'string'}],
                'comparison_operator': 'le',
                'statistic': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'period': 180,
            }
        }
        if explicit_project_constraint:
            project_constraint = {'field': 'project_id', 'op': 'eq',
                                  'value': 'aprojectidthatisnotmine'}
            json['threshold_rule']['query'].append(project_constraint)
        headers = {}
        headers.update(self.auth_headers)
        headers['X-Roles'] = 'admin'
        self.post_json('/alarms', params=json, status=201,
                       headers=headers)
        alarms = list(self.conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))
        self.assertEqual('auseridthatisnotmine', alarms[0].user_id)
        self.assertEqual('aprojectidthatisnotmine', alarms[0].project_id)
        self._add_default_threshold_rule(json)
        if alarms[0].name == 'added_alarm':
            for key in json:
                if key.endswith('_rule'):
                    storage_key = 'rule'
                    if explicit_project_constraint:
                        self.assertEqual(json[key],
                                         getattr(alarms[0], storage_key))
                    else:
                        query = getattr(alarms[0], storage_key).get('query')
                        self.assertEqual(2, len(query))
                        implicit_constraint = {
                            u'field': u'project_id',
                            u'value': u'aprojectidthatisnotmine',
                            u'op': u'eq'
                        }
                        self.assertEqual(implicit_constraint, query[1])
                else:
                    self.assertEqual(json[key], getattr(alarms[0], key))
        else:
            self.fail("Alarm not found")

    def test_post_alarm_as_admin_explicit_project_constraint(self):
        """Test the creation of an alarm as admin for another project,
        with an explicit query constraint on the owner's project ID.
        """
        self._do_test_post_alarm_as_admin(True)

    def test_post_alarm_as_admin_implicit_project_constraint(self):
        """Test the creation of an alarm as admin for another project,
        without an explicit query constraint on the owner's project ID.
        """
        self._do_test_post_alarm_as_admin(False)

    def test_post_alarm_as_admin_no_user(self):
        """Test the creation of an alarm as admin for another project but
        forgetting to set the values.
        """
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'threshold',
            'project_id': 'aprojectidthatisnotmine',
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.field',
                           'op': 'eq',
                           'value': '5',
                           'type': 'string'},
                          {'field': 'project_id', 'op': 'eq',
                           'value': 'aprojectidthatisnotmine'}],
                'comparison_operator': 'le',
                'statistic': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'period': 180,
            }
        }
        headers = {}
        headers.update(self.auth_headers)
        headers['X-Roles'] = 'admin'
        self.post_json('/alarms', params=json, status=201,
                       headers=headers)
        alarms = list(self.conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))
        self.assertEqual(self.auth_headers['X-User-Id'], alarms[0].user_id)
        self.assertEqual('aprojectidthatisnotmine', alarms[0].project_id)
        self._verify_alarm(json, alarms[0], 'added_alarm')

    def test_post_alarm_as_admin_no_project(self):
        """Test the creation of an alarm as admin for another project but
        forgetting to set the values.
        """
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'threshold',
            'user_id': 'auseridthatisnotmine',
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.field',
                           'op': 'eq',
                           'value': '5',
                           'type': 'string'},
                          {'field': 'project_id', 'op': 'eq',
                           'value': 'aprojectidthatisnotmine'}],
                'comparison_operator': 'le',
                'statistic': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'period': 180,
            }
        }
        headers = {}
        headers.update(self.auth_headers)
        headers['X-Roles'] = 'admin'
        self.post_json('/alarms', params=json, status=201,
                       headers=headers)
        alarms = list(self.conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))
        self.assertEqual('auseridthatisnotmine', alarms[0].user_id)
        self.assertEqual(self.auth_headers['X-Project-Id'],
                         alarms[0].project_id)
        self._verify_alarm(json, alarms[0], 'added_alarm')

    @staticmethod
    def _alarm_representation_owned_by(identifiers):
        json = {
            'name': 'added_alarm',
            'enabled': False,
            'type': 'threshold',
            'ok_actions': ['http://something/ok'],
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.field',
                           'op': 'eq',
                           'value': '5',
                           'type': 'string'}],
                'comparison_operator': 'le',
                'statistic': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'period': 180,
            }
        }
        for aspect, id in identifiers.iteritems():
            json['%s_id' % aspect] = id
        return json

    def _do_test_post_alarm_as_nonadmin_on_behalf_of_another(self,
                                                             identifiers):
        """Test that posting an alarm as non-admin on behalf of another
        user/project fails with an explicit 401 instead of reverting
        to the requestor's identity.
        """
        json = self._alarm_representation_owned_by(identifiers)
        headers = {}
        headers.update(self.auth_headers)
        headers['X-Roles'] = 'demo'
        resp = self.post_json('/alarms', params=json, status=401,
                              headers=headers)
        aspect = 'user' if 'user' in identifiers else 'project'
        params = dict(aspect=aspect, id=identifiers[aspect])
        self.assertEqual("Not Authorized to access %(aspect)s %(id)s" % params,
                         jsonutils.loads(resp.body)['error_message']
                         ['faultstring'])

    def test_post_alarm_as_nonadmin_on_behalf_of_another_user(self):
        identifiers = dict(user='auseridthatisnotmine')
        self._do_test_post_alarm_as_nonadmin_on_behalf_of_another(identifiers)

    def test_post_alarm_as_nonadmin_on_behalf_of_another_project(self):
        identifiers = dict(project='aprojectidthatisnotmine')
        self._do_test_post_alarm_as_nonadmin_on_behalf_of_another(identifiers)

    def test_post_alarm_as_nonadmin_on_behalf_of_another_creds(self):
        identifiers = dict(user='auseridthatisnotmine',
                           project='aprojectidthatisnotmine')
        self._do_test_post_alarm_as_nonadmin_on_behalf_of_another(identifiers)

    def _do_test_post_alarm_as_nonadmin_on_behalf_of_self(self, identifiers):
        """Test posting an alarm as non-admin on behalf of own user/project
        creates alarm associated with the requestor's identity.
        """
        json = self._alarm_representation_owned_by(identifiers)
        headers = {}
        headers.update(self.auth_headers)
        headers['X-Roles'] = 'demo'
        self.post_json('/alarms', params=json, status=201, headers=headers)
        alarms = list(self.conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))
        self.assertEqual(alarms[0].user_id,
                         self.auth_headers['X-User-Id'])
        self.assertEqual(alarms[0].project_id,
                         self.auth_headers['X-Project-Id'])

    def test_post_alarm_as_nonadmin_on_behalf_of_own_user(self):
        identifiers = dict(user=self.auth_headers['X-User-Id'])
        self._do_test_post_alarm_as_nonadmin_on_behalf_of_self(identifiers)

    def test_post_alarm_as_nonadmin_on_behalf_of_own_project(self):
        identifiers = dict(project=self.auth_headers['X-Project-Id'])
        self._do_test_post_alarm_as_nonadmin_on_behalf_of_self(identifiers)

    def test_post_alarm_as_nonadmin_on_behalf_of_own_creds(self):
        identifiers = dict(user=self.auth_headers['X-User-Id'],
                           project=self.auth_headers['X-Project-Id'])
        self._do_test_post_alarm_as_nonadmin_on_behalf_of_self(identifiers)

    def test_post_alarm_combination(self):
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'combination',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'combination_rule': {
                'alarm_ids': ['a',
                              'b'],
                'operator': 'and',
            }
        }
        self.post_json('/alarms', params=json, status=201,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))
        if alarms[0].name == 'added_alarm':
            for key in json:
                if key.endswith('_rule'):
                    storage_key = 'rule'
                else:
                    storage_key = key
                self.assertEqual(json[key], getattr(alarms[0], storage_key))
        else:
            self.fail("Alarm not found")

    def test_post_combination_alarm_as_user_with_unauthorized_alarm(self):
        """Test that post a combination alarm as normal user/project
        with an alarm_id unauthorized for this project/user
        """
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'combination',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'combination_rule': {
                'alarm_ids': ['a',
                              'b'],
                'operator': 'and',
            }
        }
        an_other_user_auth = {'X-User-Id': str(uuid.uuid4()),
                              'X-Project-Id': str(uuid.uuid4())}
        resp = self.post_json('/alarms', params=json, status=404,
                              headers=an_other_user_auth)
        self.assertEqual("Alarm a Not Found",
                         jsonutils.loads(resp.body)['error_message']
                         ['faultstring'])

    def test_post_combination_alarm_as_admin_on_behalf_of_an_other_user(self):
        """Test that post a combination alarm as admin on behalf of an other
        user/project with an alarm_id unauthorized for this project/user
        """
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'user_id': 'auseridthatisnotmine',
            'project_id': 'aprojectidthatisnotmine',
            'type': 'combination',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'combination_rule': {
                'alarm_ids': ['a',
                              'b'],
                'operator': 'and',
            }
        }

        headers = {}
        headers.update(self.auth_headers)
        headers['X-Roles'] = 'admin'
        resp = self.post_json('/alarms', params=json, status=404,
                              headers=headers)
        self.assertEqual("Alarm a Not Found",
                         jsonutils.loads(resp.body)['error_message']
                         ['faultstring'])

    def test_post_combination_alarm_with_reasonable_description(self):
        """Test that post a combination alarm with two blanks around the
        operator in alarm description.
        """
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'combination',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'combination_rule': {
                'alarm_ids': ['a',
                              'b'],
                'operator': 'and',
            }
        }
        self.post_json('/alarms', params=json, status=201,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms(enabled=False))
        self.assertEqual(1, len(alarms))
        self.assertEqual(u'Combined state of alarms a and b',
                         alarms[0].description)

    def test_post_combination_alarm_as_admin_success_owner_unset(self):
        self._do_post_combination_alarm_as_admin_success(False)

    def test_post_combination_alarm_as_admin_success_owner_set(self):
        self._do_post_combination_alarm_as_admin_success(True)

    def test_post_combination_alarm_with_threshold_rule(self):
        """Test the creation of an combination alarm with threshold rule.
        """
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'combination',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.field',
                           'op': 'eq',
                           'value': '5',
                           'type': 'string'}],
                'comparison_operator': 'le',
                'statistic': 'count',
                'threshold': 50,
                'evaluation_periods': '3',
                'period': '180',
            }
        }
        resp = self.post_json('/alarms', params=json,
                              expect_errors=True, status=400,
                              headers=self.auth_headers)
        self.assertEqual(
            "combination_rule must be set for combination type alarm",
            resp.json['error_message']['faultstring'])

    def test_post_threshold_alarm_with_combination_rule(self):
        """Test the creation of an threshold alarm with combination rule.
        """
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'threshold',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'combination_rule': {
                'alarm_ids': ['a',
                              'b'],
                'operator': 'and',
            }
        }
        resp = self.post_json('/alarms', params=json,
                              expect_errors=True, status=400,
                              headers=self.auth_headers)
        self.assertEqual(
            "threshold_rule must be set for threshold type alarm",
            resp.json['error_message']['faultstring'])

    def _do_post_combination_alarm_as_admin_success(self, owner_is_set):
        """Test that post a combination alarm as admin on behalf of nobody
        with an alarm_id of someone else, with owner set or not
        """
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'combination',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'combination_rule': {
                'alarm_ids': ['a',
                              'b'],
                'operator': 'and',
            }
        }
        an_other_admin_auth = {'X-User-Id': str(uuid.uuid4()),
                               'X-Project-Id': str(uuid.uuid4()),
                               'X-Roles': 'admin'}
        if owner_is_set:
            json['project_id'] = an_other_admin_auth['X-Project-Id']
            json['user_id'] = an_other_admin_auth['X-User-Id']

        self.post_json('/alarms', params=json, status=201,
                       headers=an_other_admin_auth)
        alarms = list(self.conn.get_alarms(enabled=False))
        if alarms[0].name == 'added_alarm':
            for key in json:
                if key.endswith('_rule'):
                    storage_key = 'rule'
                else:
                    storage_key = key
                self.assertEqual(json[key], getattr(alarms[0], storage_key))
        else:
            self.fail("Alarm not found")

    def test_post_invalid_alarm_combination(self):
        """Test that post a combination alarm with a not existing alarm id
        """
        json = {
            'enabled': False,
            'name': 'added_alarm',
            'state': 'ok',
            'type': 'combination',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'combination_rule': {
                'alarm_ids': ['not_exists',
                              'b'],
                'operator': 'and',
            }
        }
        self.post_json('/alarms', params=json, status=404,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms(enabled=False))
        self.assertEqual(0, len(alarms))

    def test_put_alarm(self):
        json = {
            'enabled': False,
            'name': 'name_put',
            'state': 'ok',
            'type': 'threshold',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.field',
                           'op': 'eq',
                           'value': '5',
                           'type': 'string'}],
                'comparison_operator': 'le',
                'statistic': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'period': 180,
            }
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
        alarm = list(self.conn.get_alarms(alarm_id=alarm_id, enabled=False))[0]
        json['threshold_rule']['query'].append({
            'field': 'project_id', 'op': 'eq',
            'value': self.auth_headers['X-Project-Id']})
        self._verify_alarm(json, alarm)

    def test_put_alarm_as_admin(self):
        json = {
            'user_id': 'myuserid',
            'project_id': 'myprojectid',
            'enabled': False,
            'name': 'name_put',
            'state': 'ok',
            'type': 'threshold',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.field',
                           'op': 'eq',
                           'value': '5',
                           'type': 'string'},
                          {'field': 'project_id', 'op': 'eq',
                           'value': 'myprojectid'}],
                'comparison_operator': 'le',
                'statistic': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'period': 180,
            }
        }
        headers = {}
        headers.update(self.auth_headers)
        headers['X-Roles'] = 'admin'

        data = self.get_json('/alarms',
                             headers=headers,
                             q=[{'field': 'name',
                                 'value': 'name1',
                                 }])
        self.assertEqual(1, len(data))
        alarm_id = data[0]['alarm_id']

        self.put_json('/alarms/%s' % alarm_id,
                      params=json,
                      headers=headers)
        alarm = list(self.conn.get_alarms(alarm_id=alarm_id, enabled=False))[0]
        self.assertEqual('myuserid', alarm.user_id)
        self.assertEqual('myprojectid', alarm.project_id)
        self._verify_alarm(json, alarm)

    def test_put_alarm_wrong_field(self):
        # Note: wsme will ignore unknown fields so will just not appear in
        # the Alarm.
        json = {
            'this_can_not_be_correct': 'ha',
            'enabled': False,
            'name': 'name1',
            'state': 'ok',
            'type': 'threshold',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.field',
                           'op': 'eq',
                           'value': '5',
                           'type': 'string'}],
                'comparison_operator': 'le',
                'statistic': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'period': 180,
            }
        }
        data = self.get_json('/alarms',
                             q=[{'field': 'name',
                                 'value': 'name1',
                                 }])
        self.assertEqual(1, len(data))
        alarm_id = data[0]['alarm_id']

        resp = self.put_json('/alarms/%s' % alarm_id,
                             params=json,
                             headers=self.auth_headers)
        self.assertEqual(200, resp.status_code)

    def test_put_alarm_with_existing_name(self):
        """Test that update a threshold alarm with an existing name.
        """
        json = {
            'enabled': False,
            'name': 'name1',
            'state': 'ok',
            'type': 'threshold',
            'ok_actions': ['http://something/ok'],
            'alarm_actions': ['http://something/alarm'],
            'insufficient_data_actions': ['http://something/no'],
            'repeat_actions': True,
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [{'field': 'metadata.field',
                           'op': 'eq',
                           'value': '5',
                           'type': 'string'}],
                'comparison_operator': 'le',
                'statistic': 'count',
                'threshold': 50,
                'evaluation_periods': 3,
                'period': 180,
            }
        }
        data = self.get_json('/alarms',
                             q=[{'field': 'name',
                                 'value': 'name2',
                                 }])
        self.assertEqual(1, len(data))
        alarm_id = data[0]['alarm_id']

        resp = self.put_json('/alarms/%s' % alarm_id,
                             expect_errors=True, status=409,
                             params=json,
                             headers=self.auth_headers)
        self.assertEqual(
            'Alarm with name=name1 exists',
            resp.json['error_message']['faultstring'])

    def test_put_alarm_combination_cannot_specify_itself(self):
        json = {
            'name': 'name4',
            'type': 'combination',
            'combination_rule': {
                'alarm_ids': ['d'],
            }
        }

        data = self.get_json('/alarms',
                             q=[{'field': 'name',
                                 'value': 'name4',
                                 }])
        self.assertEqual(1, len(data))
        alarm_id = data[0]['alarm_id']

        resp = self.put_json('/alarms/%s' % alarm_id,
                             expect_errors=True, status=400,
                             params=json,
                             headers=self.auth_headers)

        msg = 'Cannot specify alarm %s itself in combination rule' % alarm_id
        self.assertEqual(msg, resp.json['error_message']['faultstring'])

    def test_delete_alarm(self):
        data = self.get_json('/alarms')
        self.assertEqual(4, len(data))

        resp = self.delete('/alarms/%s' % data[0]['alarm_id'],
                           headers=self.auth_headers,
                           status=204)
        self.assertEqual('', resp.body)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_get_state_alarm(self):
        data = self.get_json('/alarms')
        self.assertEqual(4, len(data))

        resp = self.get_json('/alarms/%s/state' % data[0]['alarm_id'],
                             headers=self.auth_headers)
        self.assertEqual(resp, data[0]['state'])

    def test_set_state_alarm(self):
        data = self.get_json('/alarms')
        self.assertEqual(4, len(data))

        resp = self.put_json('/alarms/%s/state' % data[0]['alarm_id'],
                             headers=self.auth_headers,
                             params='alarm')
        alarms = list(self.conn.get_alarms(alarm_id=data[0]['alarm_id']))
        self.assertEqual(1, len(alarms))
        self.assertEqual('alarm', alarms[0].state)
        self.assertEqual('alarm', resp.json)

    def test_set_invalid_state_alarm(self):
        data = self.get_json('/alarms')
        self.assertEqual(4, len(data))

        self.put_json('/alarms/%s/state' % data[0]['alarm_id'],
                      headers=self.auth_headers,
                      params='not valid',
                      status=400)

    def _get_alarm(self, id):
        data = self.get_json('/alarms')
        match = [a for a in data if a['alarm_id'] == id]
        self.assertEqual(1, len(match), 'alarm %s not found' % id)
        return match[0]

    def _get_alarm_history(self, alarm, auth_headers=None, query=None,
                           expect_errors=False, status=200):
        url = '/alarms/%s/history' % alarm['alarm_id']
        if query:
            url += '?q.op=%(op)s&q.value=%(value)s&q.field=%(field)s' % query
        resp = self.get_json(url,
                             headers=auth_headers or self.auth_headers,
                             expect_errors=expect_errors)
        if expect_errors:
            self.assertEqual(status, resp.status_code)
        return resp

    def _update_alarm(self, alarm, updated_data, auth_headers=None):
        data = self._get_alarm(alarm['alarm_id'])
        data.update(updated_data)
        self.put_json('/alarms/%s' % alarm['alarm_id'],
                      params=data,
                      headers=auth_headers or self.auth_headers)

    def _delete_alarm(self, alarm, auth_headers=None):
        self.delete('/alarms/%s' % alarm['alarm_id'],
                    headers=auth_headers or self.auth_headers,
                    status=204)

    def _assert_is_subset(self, expected, actual):
        for k, v in expected.iteritems():
            self.assertEqual(v, actual.get(k), 'mismatched field: %s' % k)
        self.assertIsNotNone(actual['event_id'])

    def _assert_in_json(self, expected, actual):
        actual = jsonutils.dumps(jsonutils.loads(actual), sort_keys=True)
        for k, v in expected.iteritems():
            fragment = jsonutils.dumps({k: v}, sort_keys=True)[1:-1]
            self.assertTrue(fragment in actual,
                            '%s not in %s' % (fragment, actual))

    def test_record_alarm_history_config(self):
        self.CONF.set_override('record_history', False, group='alarm')
        alarm = self._get_alarm('a')
        history = self._get_alarm_history(alarm)
        self.assertEqual([], history)
        self._update_alarm(alarm, dict(name='renamed'))
        history = self._get_alarm_history(alarm)
        self.assertEqual([], history)
        self.CONF.set_override('record_history', True, group='alarm')
        self._update_alarm(alarm, dict(name='foobar'))
        history = self._get_alarm_history(alarm)
        self.assertEqual(1, len(history))

    def test_get_recorded_alarm_history_on_create(self):
        new_alarm = {
            'name': 'new_alarm',
            'type': 'threshold',
            'threshold_rule': {
                'meter_name': 'ameter',
                'query': [],
                'comparison_operator': 'le',
                'statistic': 'max',
                'threshold': 42.0,
                'period': 60,
                'evaluation_periods': 1,
            }
        }
        self.post_json('/alarms', params=new_alarm, status=201,
                       headers=self.auth_headers)

        alarms = self.get_json('/alarms',
                               q=[{'field': 'name',
                                   'value': 'new_alarm',
                                   }])
        self.assertEqual(1, len(alarms))
        alarm = alarms[0]

        history = self._get_alarm_history(alarm)
        self.assertEqual(1, len(history))
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    on_behalf_of=alarm['project_id'],
                                    project_id=alarm['project_id'],
                                    type='creation',
                                    user_id=alarm['user_id']),
                               history[0])
        self._add_default_threshold_rule(new_alarm)
        new_alarm['rule'] = new_alarm['threshold_rule']
        del new_alarm['threshold_rule']
        new_alarm['rule']['query'].append({
            'field': 'project_id', 'op': 'eq',
            'value': self.auth_headers['X-Project-Id']})
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
        data = dict(name='renamed')
        detail = '{"name": "renamed"}'
        self._do_test_get_recorded_alarm_history_on_update(data,
                                                           'rule change',
                                                           detail)

    def test_get_recorded_alarm_history_state_transition_on_behalf_of(self):
        # credentials for new non-admin user, on who's behalf the alarm
        # is created
        member_user = str(uuid.uuid4())
        member_project = str(uuid.uuid4())
        member_auth = {'X-Roles': 'member',
                       'X-User-Id': member_user,
                       'X-Project-Id': member_project}
        new_alarm = {
            'name': 'new_alarm',
            'type': 'threshold',
            'state': 'ok',
            'threshold_rule': {
                'meter_name': 'other_meter',
                'query': [{'field': 'project_id',
                           'op': 'eq',
                           'value': member_project}],
                'comparison_operator': 'le',
                'statistic': 'max',
                'threshold': 42.0,
                'evaluation_periods': 1,
                'period': 60
            }
        }
        self.post_json('/alarms', params=new_alarm, status=201,
                       headers=member_auth)
        alarm = self.get_json('/alarms', headers=member_auth)[0]

        # effect a state transition as a new administrative user
        admin_user = str(uuid.uuid4())
        admin_project = str(uuid.uuid4())
        admin_auth = {'X-Roles': 'admin',
                      'X-User-Id': admin_user,
                      'X-Project-Id': admin_project}
        data = dict(state='alarm')
        self._update_alarm(alarm, data, auth_headers=admin_auth)

        self._add_default_threshold_rule(new_alarm)
        new_alarm['rule'] = new_alarm['threshold_rule']
        del new_alarm['threshold_rule']

        # ensure that both the creation event and state transition
        # are visible to the non-admin alarm owner and admin user alike
        for auth in [member_auth, admin_auth]:
            history = self._get_alarm_history(alarm, auth_headers=auth)
            self.assertEqual(2, len(history), 'hist: %s' % history)
            self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                        detail='{"state": "alarm"}',
                                        on_behalf_of=alarm['project_id'],
                                        project_id=admin_project,
                                        type='rule change',
                                        user_id=admin_user),
                                   history[0])
            self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                        on_behalf_of=alarm['project_id'],
                                        project_id=member_project,
                                        type='creation',
                                        user_id=member_user),
                                   history[1])
            self._assert_in_json(new_alarm, history[1]['detail'])

            # ensure on_behalf_of cannot be constrained in an API call
            query = dict(field='on_behalf_of',
                         op='eq',
                         value=alarm['project_id'])
            self._get_alarm_history(alarm, auth_headers=auth, query=query,
                                    expect_errors=True, status=400)

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
                    status=204)
        history = self._get_alarm_history(alarm)
        self.assertEqual(2, len(history))
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    on_behalf_of=alarm['project_id'],
                                    project_id=alarm['project_id'],
                                    type='deletion',
                                    user_id=alarm['user_id']),
                               history[0])
        alarm['rule'] = alarm['threshold_rule']
        del alarm['threshold_rule']
        self._assert_in_json(alarm, history[0]['detail'])
        detail = '{"name": "renamed"}'
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    detail=detail,
                                    on_behalf_of=alarm['project_id'],
                                    project_id=alarm['project_id'],
                                    type='rule change',
                                    user_id=alarm['user_id']),
                               history[1])

    def test_get_alarm_history_ordered_by_recentness(self):
        alarm = self._get_alarm('a')
        for i in moves.xrange(10):
            self._update_alarm(alarm, dict(name='%s' % i))
        alarm = self._get_alarm('a')
        self._delete_alarm(alarm)
        history = self._get_alarm_history(alarm)
        self.assertEqual(11, len(history), 'hist: %s' % history)
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    type='deletion'),
                               history[0])
        alarm['rule'] = alarm['threshold_rule']
        del alarm['threshold_rule']
        self._assert_in_json(alarm, history[0]['detail'])
        for i in moves.xrange(1, 10):
            detail = '{"name": "%s"}' % (10 - i)
            self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                        detail=detail,
                                        type='rule change'),
                                   history[i])

    def test_get_alarm_history_constrained_by_timestamp(self):
        alarm = self._get_alarm('a')
        self._update_alarm(alarm, dict(name='renamed'))
        after = datetime.datetime.utcnow().isoformat()
        query = dict(field='timestamp', op='gt', value=after)
        history = self._get_alarm_history(alarm, query=query)
        self.assertEqual(0, len(history))
        query['op'] = 'le'
        history = self._get_alarm_history(alarm, query=query)
        self.assertEqual(1, len(history))
        detail = '{"name": "renamed"}'
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    detail=detail,
                                    on_behalf_of=alarm['project_id'],
                                    project_id=alarm['project_id'],
                                    type='rule change',
                                    user_id=alarm['user_id']),
                               history[0])

    def test_get_alarm_history_constrained_by_type(self):
        alarm = self._get_alarm('a')
        self._delete_alarm(alarm)
        query = dict(field='type', op='eq', value='deletion')
        history = self._get_alarm_history(alarm, query=query)
        self.assertEqual(1, len(history))
        self._assert_is_subset(dict(alarm_id=alarm['alarm_id'],
                                    on_behalf_of=alarm['project_id'],
                                    project_id=alarm['project_id'],
                                    type='deletion',
                                    user_id=alarm['user_id']),
                               history[0])
        alarm['rule'] = alarm['threshold_rule']
        del alarm['threshold_rule']
        self._assert_in_json(alarm, history[0]['detail'])

    def test_get_nonexistent_alarm_history(self):
        # the existence of alarm history is independent of the
        # continued existence of the alarm itself
        history = self._get_alarm_history(dict(alarm_id='foobar'))
        self.assertEqual([], history)

    def test_alarms_sends_notification(self):
        # Hit the AlarmsController ...
        json = {
            'name': 'sent_notification',
            'type': 'threshold',
            'threshold_rule': {
                'meter_name': 'ameter',
                'comparison_operator': 'gt',
                'threshold': 2.0,
                'statistic': 'avg',
            }

        }
        with mock.patch('ceilometer.openstack.common.notifier.api.notify') \
                as notifier:
            self.post_json('/alarms', params=json, headers=self.auth_headers)

        calls = notifier.call_args_list
        self.assertEqual(1, len(calls))
        args, _ = calls[0]
        context, publisher, event_type, priority, payload = args
        self.assertTrue(publisher.startswith('ceilometer.api'))
        self.assertEqual('alarm.creation', event_type)
        self.assertEqual('INFO', priority)
        self.assertEqual('sent_notification', payload['detail']['name'])
        self.assertTrue(set(['alarm_id', 'detail', 'event_id', 'on_behalf_of',
                             'project_id', 'timestamp', 'type',
                             'user_id']).issubset(payload.keys()))

    def test_alarm_sends_notification(self):
        # Hit the AlarmController (with alarm_id supplied) ...
        data = self.get_json('/alarms')
        with mock.patch('ceilometer.openstack.common.notifier.api.notify') \
                as notifier:
            self.delete('/alarms/%s' % data[0]['alarm_id'],
                        headers=self.auth_headers, status=204)

        calls = notifier.call_args_list
        self.assertEqual(1, len(calls))
        args, _ = calls[0]
        context, publisher, event_type, priority, payload = args
        self.assertTrue(publisher.startswith('ceilometer.api'))
        self.assertEqual('alarm.deletion', event_type)
        self.assertEqual('INFO', priority)
        self.assertEqual('name1', payload['detail']['name'])
        self.assertTrue(set(['alarm_id', 'detail', 'event_id', 'on_behalf_of',
                             'project_id', 'timestamp', 'type',
                             'user_id']).issubset(payload.keys()))
