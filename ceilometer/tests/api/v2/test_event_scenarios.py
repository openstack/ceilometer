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

import webtest.app

from ceilometer.event.storage import models
from ceilometer.tests.api import v2
from ceilometer.tests import db as tests_db

headers = {"X-Roles": "admin"}


class EventTestBase(v2.FunctionalTest,
                    tests_db.MixinTestsWithBackendScenarios):

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
        data = self.get_json(self.PATH, headers=headers)
        for event_type in ['Foo', 'Bar', 'Zoo']:
            self.assertIn(event_type, data)


class TestTraitAPI(EventTestBase):

    PATH = '/event_types/%s/traits'

    def test_get_traits_for_event(self):
        path = self.PATH % "Foo"
        data = self.get_json(path, headers=headers)

        self.assertEqual(4, len(data))

    def test_get_event_invalid_path(self):
        data = self.get_json('/event_types/trait_A/', headers=headers,
                             expect_errors=True)
        self.assertEqual(404, data.status_int)

    def test_get_traits_for_non_existent_event(self):
        path = self.PATH % "NO_SUCH_EVENT_TYPE"
        data = self.get_json(path, headers=headers)

        self.assertEqual([], data)

    def test_get_trait_data_for_event(self):
        path = (self.PATH % "Foo") + "/trait_A"
        data = self.get_json(path, headers=headers)
        self.assertEqual(1, len(data))
        self.assertEqual("trait_A", data[0]['name'])

        path = (self.PATH % "Foo") + "/trait_B"
        data = self.get_json(path, headers=headers)
        self.assertEqual(1, len(data))
        self.assertEqual("trait_B", data[0]['name'])
        self.assertEqual("1", data[0]['value'])

        path = (self.PATH % "Foo") + "/trait_D"
        data = self.get_json(path, headers=headers)
        self.assertEqual(1, len(data))
        self.assertEqual("trait_D", data[0]['name'])
        self.assertEqual((self.trait_time - datetime.timedelta(days=3)).
                         isoformat(), data[0]['value'])

    def test_get_trait_data_for_non_existent_event(self):
        path = (self.PATH % "NO_SUCH_EVENT") + "/trait_A"
        data = self.get_json(path, headers=headers)

        self.assertEqual([], data)

    def test_get_trait_data_for_non_existent_trait(self):
        path = (self.PATH % "Foo") + "/no_such_trait"
        data = self.get_json(path, headers=headers)

        self.assertEqual([], data)


class TestEventAPI(EventTestBase):

    PATH = '/events'

    def test_get_events(self):
        data = self.get_json(self.PATH, headers=headers)
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
        event = self.get_json(self.PATH + "/100", headers=headers)
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
        data = self.get_json(self.PATH + "/DNE", headers=headers,
                             expect_errors=True)
        self.assertEqual(404, data.status_int)

    def test_get_events_filter_event_type(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'event_type',
                                 'value': 'Foo'}])
        self.assertEqual(1, len(data))

    def test_get_events_filter_trait_no_type(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text'}])
        self.assertEqual(1, len(data))
        self.assertEqual('Foo', data[0]['event_type'])

    def test_get_events_filter_trait_empty_type(self):
        return
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': ''}])
        self.assertEqual(1, len(data))
        self.assertEqual('Foo', data[0]['event_type'])

    def test_get_events_filter_trait_invalid_type(self):
        resp = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'whats-up'}],
                             expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertEqual("The data type whats-up is not supported. The "
                         "supported data type list is: [\'integer\', "
                         "\'float\', \'string\', \'datetime\']",
                         resp.json['error_message']['faultstring'])

    def test_get_events_filter_text_trait(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'string'}])
        self.assertEqual(1, len(data))
        self.assertEqual('Foo', data[0]['event_type'])

    def test_get_events_filter_int_trait(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_B',
                                 'value': '101',
                                 'type': 'integer'}])
        self.assertEqual(1, len(data))
        self.assertEqual('Bar', data[0]['event_type'])

        traits = filter(lambda x: x['name'] == 'trait_B', data[0]['traits'])
        self.assertEqual(1, len(traits))
        self.assertEqual('integer', traits[0]['type'])
        self.assertEqual('101', traits[0]['value'])

    def test_get_events_filter_float_trait(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_C',
                                 'value': '200.123456',
                                 'type': 'float'}])
        self.assertEqual(1, len(data))
        self.assertEqual('Zoo', data[0]['event_type'])

        traits = filter(lambda x: x['name'] == 'trait_C', data[0]['traits'])
        self.assertEqual(1, len(traits))
        self.assertEqual('float', traits[0]['type'])
        self.assertEqual('200.123456', traits[0]['value'])

    def test_get_events_filter_datetime_trait(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_D',
                                 'value': '2014-01-01T05:00:00',
                                 'type': 'datetime'}])
        self.assertEqual(1, len(data))
        traits = filter(lambda x: x['name'] == 'trait_D', data[0]['traits'])
        self.assertEqual(1, len(traits))
        self.assertEqual('datetime', traits[0]['type'])
        self.assertEqual('2014-01-01T05:00:00', traits[0]['value'])

    def test_get_events_multiple_filters(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_B',
                                 'value': '1',
                                 'type': 'integer'},
                                {'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'string'}])
        self.assertEqual(1, len(data))
        self.assertEqual('Foo', data[0]['event_type'])

    def test_get_events_multiple_filters_no_matches(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_B',
                                 'value': '101',
                                 'type': 'integer'},
                                {'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'string'}])

        self.assertEqual(0, len(data))

    def test_get_events_multiple_filters_same_field_different_values(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'string'},
                                {'field': 'trait_A',
                                 'value': 'my_Bar_text',
                                 'type': 'string'}])
        self.assertEqual(0, len(data))

    def test_get_events_not_filters(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[])
        self.assertEqual(3, len(data))

    def test_get_events_filter_op_string(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'string',
                                 'op': 'eq'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Bar_text',
                                 'type': 'string',
                                 'op': 'lt'}])
        self.assertEqual(0, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Zoo_text',
                                 'type': 'string',
                                 'op': 'le'}])
        self.assertEqual(3, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Foo_text',
                                 'type': 'string',
                                 'op': 'ne'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Bar_text',
                                 'type': 'string',
                                 'op': 'gt'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_A',
                                 'value': 'my_Zoo_text',
                                 'type': 'string',
                                 'op': 'ge'}])
        self.assertEqual(1, len(data))

    def test_get_events_filter_op_integer(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_B',
                                 'value': '101',
                                 'type': 'integer',
                                 'op': 'eq'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_B',
                                 'value': '201',
                                 'type': 'integer',
                                 'op': 'lt'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_B',
                                 'value': '1',
                                 'type': 'integer',
                                 'op': 'le'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_B',
                                 'value': '101',
                                 'type': 'integer',
                                 'op': 'ne'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_B',
                                 'value': '201',
                                 'type': 'integer',
                                 'op': 'gt'}])
        self.assertEqual(0, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_B',
                                 'value': '1',
                                 'type': 'integer',
                                 'op': 'ge'}])
        self.assertEqual(3, len(data))

    def test_get_events_filter_op_float(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_C',
                                 'value': '100.123456',
                                 'type': 'float',
                                 'op': 'eq'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_C',
                                 'value': '200.123456',
                                 'type': 'float',
                                 'op': 'lt'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_C',
                                 'value': '0.123456',
                                 'type': 'float',
                                 'op': 'le'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_C',
                                 'value': '100.123456',
                                 'type': 'float',
                                 'op': 'ne'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_C',
                                 'value': '200.123456',
                                 'type': 'float',
                                 'op': 'gt'}])
        self.assertEqual(0, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_C',
                                 'value': '0.123456',
                                 'type': 'float',
                                 'op': 'ge'}])
        self.assertEqual(3, len(data))

    def test_get_events_filter_op_datatime(self):
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_D',
                                 'value': '2014-01-01T05:00:00',
                                 'type': 'datetime',
                                 'op': 'eq'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_D',
                                 'value': '2014-01-02T05:00:00',
                                 'type': 'datetime',
                                 'op': 'lt'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_D',
                                 'value': '2013-12-31T05:00:00',
                                 'type': 'datetime',
                                 'op': 'le'}])
        self.assertEqual(1, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_D',
                                 'value': '2014-01-01T05:00:00',
                                 'type': 'datetime',
                                 'op': 'ne'}])
        self.assertEqual(2, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_D',
                                 'value': '2014-01-02T05:00:00',
                                 'type': 'datetime',
                                 'op': 'gt'}])
        self.assertEqual(0, len(data))
        data = self.get_json(self.PATH, headers=headers,
                             q=[{'field': 'trait_D',
                                 'value': '2013-12-31T05:00:00',
                                 'type': 'datetime',
                                 'op': 'ge'}])
        self.assertEqual(3, len(data))

    def test_get_events_filter_wrong_op(self):
        self.assertRaises(webtest.app.AppError,
                          self.get_json, self.PATH, headers=headers,
                          q=[{'field': 'trait_B',
                              'value': '1',
                              'type': 'integer',
                              'op': 'el'}])
