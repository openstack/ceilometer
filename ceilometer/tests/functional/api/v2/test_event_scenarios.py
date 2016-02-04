#
# Copyright 2013 Hewlett-Packard Development Company, L.P.
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
"""Test event, event_type and trait retrieval."""

import datetime
import uuid

import webtest.app

from ceilometer.event.storage import models
from ceilometer.tests import db as tests_db
from ceilometer.tests.functional.api import v2

USER_ID = uuid.uuid4().hex
PROJ_ID = uuid.uuid4().hex
HEADERS = {"X-Roles": "admin",
           "X-User-Id": USER_ID,
           "X-Project-Id": PROJ_ID}


class EventTestBase(v2.FunctionalTest):

    def setUp(self):
        super(EventTestBase, self).setUp()
        self._generate_models()

    def _generate_models(self):
        event_models = []
        base = 0
        self.s_time = datetime.datetime(2013, 12, 31, 5, 0)
        self.trait_time = datetime.datetime(2013, 12, 31, 5, 0)
        for event_type in ['Foo', 'Bar', 'Zoo']:
            trait_models = [models.Trait(name, type, value)
                            for name, type, value in [
                                ('trait_A', models.Trait.TEXT_TYPE,
                                    "my_%s_text" % event_type),
                                ('trait_B', models.Trait.INT_TYPE,
                                    base + 1),
                                ('trait_C', models.Trait.FLOAT_TYPE,
                                    float(base) + 0.123456),
                                ('trait_D', models.Trait.DATETIME_TYPE,
                                    self.trait_time)]]

            # Message ID for test will be 'base'. So, message ID for the first
            # event will be '0', the second '100', and so on.
            # trait_time in first event will be equal to self.trait_time
            # (datetime.datetime(2013, 12, 31, 5, 0)), next will add 1 day, so
            # second will be (datetime.datetime(2014, 01, 01, 5, 0)) and so on.
            event_models.append(
                models.Event(message_id=str(base),
                             event_type=event_type,
                             generated=self.trait_time,
                             traits=trait_models,
                             raw={'status': {'nested': 'started'}}))
            base += 100
            self.trait_time += datetime.timedelta(days=1)
        self.event_conn.record_events(event_models)


class TestEventTypeAPI(EventTestBase):

    PATH = '/event_types'

    def test_event_types(self):
        data = self.get_json(self.PATH, headers=HEADERS)
        for event_type in ['Foo', 'Bar', 'Zoo']:
            self.assertIn(event_type, data)


class TestTraitAPI(EventTestBase):

    PATH = '/event_types/%s/traits'

    def test_get_traits_for_event(self):
        path = self.PATH % "Foo"
        data = self.get_json(path, headers=HEADERS)

        self.assertEqual(4, len(data))

    def test_get_event_invalid_path(self):
        data = self.get_json('/event_types/trait_A/', headers=HEADERS,
                             expect_errors=True)
        self.assertEqual(404, data.status_int)

    def test_get_traits_for_non_existent_event(self):
        path = self.PATH % "NO_SUCH_EVENT_TYPE"
        data = self.get_json(path, headers=HEADERS)

        self.assertEqual([], data)

    def test_get_trait_data_for_event(self):
        path = (self.PATH % "Foo") + "/trait_A"
        data = self.get_json(path, headers=HEADERS)
        self.assertEqual(1, len(data))
        self.assertEqual("trait_A", data[0]['name'])

        path = (self.PATH % "Foo") + "/trait_B"
        data = self.get_json(path, headers=HEADERS)
        self.assertEqual(1, len(data))
        self.assertEqual("trait_B", data[0]['name'])
        self.assertEqual("1", data[0]['value'])

        path = (self.PATH % "Foo") + "/trait_D"
        data = self.get_json(path, headers=HEADERS)
        self.assertEqual(1, len(data))
        self.assertEqual("trait_D", data[0]['name'])
        self.assertEqual((self.trait_time - datetime.timedelta(days=3)).
                         isoformat(), data[0]['value'])

    def test_get_trait_data_for_non_existent_event(self):
        path = (self.PATH % "NO_SUCH_EVENT") + "/trait_A"
        data = self.get_json(path, headers=HEADERS)

        self.assertEqual([], data)

    def test_get_trait_data_for_non_existent_trait(self):
        path = (self.PATH % "Foo") + "/no_such_trait"
        data = self.get_json(path, headers=HEADERS)

        self.assertEqual([], data)


class TestEventAPI(EventTestBase):

    PATH = '/events'

    def test_get_events(self):
        data = self.get_json(self.PATH, headers=HEADERS)
        self.assertEqual(3, len(data))
        # We expect to get native UTC generated time back
        trait_time = self.s_time
        for event in data:
            expected_generated = trait_time.isoformat()
            self.assertIn(event['event_type'], ['Foo', 'Bar', 'Zoo'])
            self.assertEqual(4, len(event['traits']))
            self.assertEqual({'status': {'nested': 'started'}}, event['raw']),
            self.assertEqual(expected_generated, event['generated'])
            for trait_name in ['trait_A', 'trait_B',
                               'trait_C', 'trait_D']:
                self.assertIn(trait_name, map(lambda x: x['name'],
                              event['traits']))
            trait_time += datetime.timedelta(days=1)

    def test_get_event_by_message_id(self):
        event = self.get_json(self.PATH + "/100", headers=HEADERS)
        expected_traits = [{'name': 'trait_A',
                            'type': 'string',
                            'value': 'my_Bar_text'},
                           {'name': 'trait_B',
                            'type': 'integer',
                            'value': '101'},
                           {'name': 'trait_C',
                            'type': 'float',
                            'value': '100.123456'},
                           {'name': 'trait_D',
                            'type': 'datetime',
                            'value': '2014-01-01T05:00:00'}]
        self.assertEqual('100', event['message_id'])
        self.assertEqual('Bar', event['event_type'])
        self.assertEqual('2014-01-01T05:00:00', event['generated'])
        self.assertEqual(expected_traits, event['traits'])

    def test_get_event_by_message_id_no_such_id(self):
        data = self.get_json(self.PATH + "/DNE", headers=HEADERS,
                             expect_errors=True)
        self.assertEqual(404, data.status_int)

    def test_get_events_filter_event_type(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'event_type',
                                 'value': 'Foo'}])
        self.assertEqual(1, len(data))

    def test_get_events_filter_trait_no_type(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text'}])
        self.assertEqual(1, len(data))
        self.assertEqual('Foo', data[0]['event_type'])

    def test_get_events_filter_trait_empty_type(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': ''}])
        self.assertEqual(1, len(data))
        self.assertEqual('Foo', data[0]['event_type'])

    def test_get_events_filter_trait_invalid_type(self):
        resp = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'whats-up'}],
                             expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertEqual("The data type whats-up is not supported. The "
                         "supported data type list is: [\'integer\', "
                         "\'float\', \'string\', \'datetime\']",
                         resp.json['error_message']['faultstring'])

    def test_get_events_filter_operator_invalid_type(self):
        resp = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'op': 'whats-up'}],
                             expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertEqual("Operator whats-up is not supported. The "
                         "supported operators are: (\'lt\', \'le\', "
                         "\'eq\', \'ne\', \'ge\', \'gt\')",
                         resp.json['error_message']['faultstring'])

    def test_get_events_filter_text_trait(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'string'}])
        self.assertEqual(1, len(data))
        self.assertEqual('Foo', data[0]['event_type'])

    def test_get_events_filter_int_trait(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_B',
                                 'value': '101',
                                 'type': 'integer'}])
        self.assertEqual(1, len(data))
        self.assertEqual('Bar', data[0]['event_type'])

        traits = [x for x in data[0]['traits'] if x['name'] == 'trait_B']
        self.assertEqual(1, len(traits))
        self.assertEqual('integer', traits[0]['type'])
        self.assertEqual('101', traits[0]['value'])

    def test_get_events_filter_float_trait(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_C',
                                 'value': '200.123456',
                                 'type': 'float'}])
        self.assertEqual(1, len(data))
        self.assertEqual('Zoo', data[0]['event_type'])

        traits = [x for x in data[0]['traits'] if x['name'] == 'trait_C']
        self.assertEqual(1, len(traits))
        self.assertEqual('float', traits[0]['type'])
        self.assertEqual('200.123456', traits[0]['value'])

    def test_get_events_filter_datetime_trait(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_D',
                                 'value': '2014-01-01T05:00:00',
                                 'type': 'datetime'}])
        self.assertEqual(1, len(data))
        traits = [x for x in data[0]['traits'] if x['name'] == 'trait_D']
        self.assertEqual(1, len(traits))
        self.assertEqual('datetime', traits[0]['type'])
        self.assertEqual('2014-01-01T05:00:00', traits[0]['value'])

    def test_get_events_multiple_filters(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_B',
                                 'value': '1',
                                 'type': 'integer'},
                                {'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'string'}])
        self.assertEqual(1, len(data))
        self.assertEqual('Foo', data[0]['event_type'])

    def test_get_events_multiple_filters_no_matches(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_B',
                                 'value': '101',
                                 'type': 'integer'},
                                {'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'string'}])

        self.assertEqual(0, len(data))

    def test_get_events_multiple_filters_same_field_different_values(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'string'},
                                {'field': 'trait_A',
                                 'value': 'my_Bar_text',
                                 'type': 'string'}])
        self.assertEqual(0, len(data))

    def test_get_events_not_filters(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[])
        self.assertEqual(3, len(data))

    def test_get_events_filter_op_string(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'string',
                                 'op': 'eq'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Bar_text',
                                 'type': 'string',
                                 'op': 'lt'}])
        self.assertEqual(0, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Zoo_text',
                                 'type': 'string',
                                 'op': 'le'}])
        self.assertEqual(3, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'string',
                                 'op': 'ne'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Bar_text',
                                 'type': 'string',
                                 'op': 'gt'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Zoo_text',
                                 'type': 'string',
                                 'op': 'ge'}])
        self.assertEqual(1, len(data))

    def test_get_events_filter_op_integer(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_B',
                                 'value': '101',
                                 'type': 'integer',
                                 'op': 'eq'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_B',
                                 'value': '201',
                                 'type': 'integer',
                                 'op': 'lt'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_B',
                                 'value': '1',
                                 'type': 'integer',
                                 'op': 'le'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_B',
                                 'value': '101',
                                 'type': 'integer',
                                 'op': 'ne'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_B',
                                 'value': '201',
                                 'type': 'integer',
                                 'op': 'gt'}])
        self.assertEqual(0, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_B',
                                 'value': '1',
                                 'type': 'integer',
                                 'op': 'ge'}])
        self.assertEqual(3, len(data))

    def test_get_events_filter_op_float(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_C',
                                 'value': '100.123456',
                                 'type': 'float',
                                 'op': 'eq'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_C',
                                 'value': '200.123456',
                                 'type': 'float',
                                 'op': 'lt'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_C',
                                 'value': '0.123456',
                                 'type': 'float',
                                 'op': 'le'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_C',
                                 'value': '100.123456',
                                 'type': 'float',
                                 'op': 'ne'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_C',
                                 'value': '200.123456',
                                 'type': 'float',
                                 'op': 'gt'}])
        self.assertEqual(0, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_C',
                                 'value': '0.123456',
                                 'type': 'float',
                                 'op': 'ge'}])
        self.assertEqual(3, len(data))

    def test_get_events_filter_op_datatime(self):
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_D',
                                 'value': '2014-01-01T05:00:00',
                                 'type': 'datetime',
                                 'op': 'eq'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_D',
                                 'value': '2014-01-02T05:00:00',
                                 'type': 'datetime',
                                 'op': 'lt'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_D',
                                 'value': '2013-12-31T05:00:00',
                                 'type': 'datetime',
                                 'op': 'le'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_D',
                                 'value': '2014-01-01T05:00:00',
                                 'type': 'datetime',
                                 'op': 'ne'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_D',
                                 'value': '2014-01-02T05:00:00',
                                 'type': 'datetime',
                                 'op': 'gt'}])
        self.assertEqual(0, len(data))
        data = self.get_json(self.PATH, headers=HEADERS,
                             q=[{'field': 'trait_D',
                                 'value': '2013-12-31T05:00:00',
                                 'type': 'datetime',
                                 'op': 'ge'}])
        self.assertEqual(3, len(data))

    def test_get_events_filter_wrong_op(self):
        self.assertRaises(webtest.app.AppError,
                          self.get_json, self.PATH, headers=HEADERS,
                          q=[{'field': 'trait_B',
                              'value': '1',
                              'type': 'integer',
                              'op': 'el'}])


class AclRestrictedEventTestBase(v2.FunctionalTest):

    def setUp(self):
        super(AclRestrictedEventTestBase, self).setUp()
        self.admin_user_id = uuid.uuid4().hex
        self.admin_proj_id = uuid.uuid4().hex
        self.user_id = uuid.uuid4().hex
        self.proj_id = uuid.uuid4().hex
        self._generate_models()

    def _generate_models(self):
        event_models = []
        self.s_time = datetime.datetime(2013, 12, 31, 5, 0)
        event_models.append(
            models.Event(message_id='1',
                         event_type='empty_ev',
                         generated=self.s_time,
                         traits=[models.Trait('random',
                                              models.Trait.TEXT_TYPE,
                                              'blah')],
                         raw={}))
        event_models.append(
            models.Event(message_id='2',
                         event_type='admin_ev',
                         generated=self.s_time,
                         traits=[models.Trait('project_id',
                                              models.Trait.TEXT_TYPE,
                                              self.admin_proj_id),
                                 models.Trait('user_id',
                                              models.Trait.TEXT_TYPE,
                                              self.admin_user_id)],
                         raw={}))
        event_models.append(
            models.Event(message_id='3',
                         event_type='user_ev',
                         generated=self.s_time,
                         traits=[models.Trait('project_id',
                                              models.Trait.TEXT_TYPE,
                                              self.proj_id),
                                 models.Trait('user_id',
                                              models.Trait.TEXT_TYPE,
                                              self.user_id)],
                         raw={}))
        self.event_conn.record_events(event_models)

    def test_non_admin_access(self):
        a_headers = {"X-Roles": "member",
                     "X-User-Id": self.user_id,
                     "X-Project-Id": self.proj_id}
        data = self.get_json('/events', headers=a_headers)
        self.assertEqual(1, len(data))
        self.assertEqual('user_ev', data[0]['event_type'])

    def test_non_admin_access_single(self):
        a_headers = {"X-Roles": "member",
                     "X-User-Id": self.user_id,
                     "X-Project-Id": self.proj_id}
        data = self.get_json('/events/3', headers=a_headers)
        self.assertEqual('user_ev', data['event_type'])

    def test_non_admin_access_incorrect_user(self):
        a_headers = {"X-Roles": "member",
                     "X-User-Id": 'blah',
                     "X-Project-Id": self.proj_id}
        data = self.get_json('/events', headers=a_headers)
        self.assertEqual(0, len(data))

    def test_non_admin_access_incorrect_proj(self):
        a_headers = {"X-Roles": "member",
                     "X-User-Id": self.user_id,
                     "X-Project-Id": 'blah'}
        data = self.get_json('/events', headers=a_headers)
        self.assertEqual(0, len(data))

    def test_non_admin_access_single_invalid(self):
        a_headers = {"X-Roles": "member",
                     "X-User-Id": self.user_id,
                     "X-Project-Id": self.proj_id}
        data = self.get_json('/events/1', headers=a_headers,
                             expect_errors=True)
        self.assertEqual(404, data.status_int)

    @tests_db.run_with('sqlite', 'mysql', 'pgsql', 'mongodb', 'es', 'db2')
    def test_admin_access(self):
        a_headers = {"X-Roles": "admin",
                     "X-User-Id": self.admin_user_id,
                     "X-Project-Id": self.admin_proj_id}
        data = self.get_json('/events', headers=a_headers)
        self.assertEqual(2, len(data))
        self.assertEqual(set(['empty_ev', 'admin_ev']),
                         set(ev['event_type'] for ev in data))

    @tests_db.run_with('sqlite', 'mysql', 'pgsql', 'mongodb', 'es', 'db2')
    def test_admin_access_trait_filter(self):
        a_headers = {"X-Roles": "admin",
                     "X-User-Id": self.admin_user_id,
                     "X-Project-Id": self.admin_proj_id}
        data = self.get_json('/events', headers=a_headers,
                             q=[{'field': 'random',
                                 'value': 'blah',
                                 'type': 'string',
                                 'op': 'eq'}])
        self.assertEqual(1, len(data))
        self.assertEqual('empty_ev', data[0]['event_type'])

    @tests_db.run_with('sqlite', 'mysql', 'pgsql', 'mongodb', 'es', 'db2')
    def test_admin_access_single(self):
        a_headers = {"X-Roles": "admin",
                     "X-User-Id": self.admin_user_id,
                     "X-Project-Id": self.admin_proj_id}
        data = self.get_json('/events/1', headers=a_headers)
        self.assertEqual('empty_ev', data['event_type'])
        data = self.get_json('/events/2', headers=a_headers)
        self.assertEqual('admin_ev', data['event_type'])

    @tests_db.run_with('sqlite', 'mysql', 'pgsql', 'mongodb', 'es', 'db2')
    def test_admin_access_trait_filter_no_access(self):
        a_headers = {"X-Roles": "admin",
                     "X-User-Id": self.admin_user_id,
                     "X-Project-Id": self.admin_proj_id}
        data = self.get_json('/events', headers=a_headers,
                             q=[{'field': 'user_id',
                                 'value': self.user_id,
                                 'type': 'string',
                                 'op': 'eq'}])
        self.assertEqual(0, len(data))


class EventRestrictionTestBase(v2.FunctionalTest):

    def setUp(self):
        super(EventRestrictionTestBase, self).setUp()
        self.CONF.set_override('default_api_return_limit', 10, group='api')
        self._generate_models()

    def _generate_models(self):
        event_models = []
        base = 0
        self.s_time = datetime.datetime(2013, 12, 31, 5, 0)
        self.trait_time = datetime.datetime(2013, 12, 31, 5, 0)
        for i in range(20):
            trait_models = [models.Trait(name, type, value)
                            for name, type, value in [
                                ('trait_A', models.Trait.TEXT_TYPE,
                                    "my_text"),
                                ('trait_B', models.Trait.INT_TYPE,
                                    base + 1),
                                ('trait_C', models.Trait.FLOAT_TYPE,
                                    float(base) + 0.123456),
                                ('trait_D', models.Trait.DATETIME_TYPE,
                                    self.trait_time)]]

            event_models.append(
                models.Event(message_id=str(uuid.uuid4()),
                             event_type='foo.bar',
                             generated=self.trait_time,
                             traits=trait_models,
                             raw={'status': {'nested': 'started'}}))
            self.trait_time += datetime.timedelta(seconds=1)
        self.event_conn.record_events(event_models)


class TestEventRestriction(EventRestrictionTestBase):

    def test_get_limit(self):
        data = self.get_json('/events?limit=1', headers=HEADERS)
        self.assertEqual(1, len(data))

    def test_get_limit_negative(self):
        self.assertRaises(webtest.app.AppError,
                          self.get_json, '/events?limit=-2', headers=HEADERS)

    def test_get_limit_bigger(self):
        data = self.get_json('/events?limit=100', headers=HEADERS)
        self.assertEqual(20, len(data))

    def test_get_default_limit(self):
        data = self.get_json('/events', headers=HEADERS)
        self.assertEqual(10, len(data))
