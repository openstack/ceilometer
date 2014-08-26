#
# Author: John Tran <jhtran@att.com>
#         Julien Danjou <julien@danjou.info>
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
"""Tests for ceilometer/storage/impl_sqlalchemy.py

.. note::
  In order to run the tests against real SQL server set the environment
  variable CEILOMETER_TEST_SQL_URL to point to a SQL server before running
  the tests.

"""

import datetime
import repr

import mock
from oslo.utils import timeutils

from ceilometer.alarm.storage import impl_sqlalchemy as impl_sqla_alarm
from ceilometer.storage import impl_sqlalchemy
from ceilometer.storage import models
from ceilometer.storage.sqlalchemy import models as sql_models
from ceilometer.tests import base as test_base
from ceilometer.tests import db as tests_db
from ceilometer.tests.storage import test_storage_scenarios as scenarios


@tests_db.run_with('sqlite')
class CeilometerBaseTest(tests_db.TestBase):

    def test_ceilometer_base(self):
        base = sql_models.CeilometerBase()
        base['key'] = 'value'
        self.assertEqual('value', base['key'])


@tests_db.run_with('sqlite')
class TraitTypeTest(tests_db.TestBase):
    # TraitType is a construct specific to sqlalchemy.
    # Not applicable to other drivers.

    def test_trait_type_exists(self):
        tt1 = self.conn._get_or_create_trait_type("foo", 0)
        self.assertTrue(tt1.id >= 0)
        tt2 = self.conn._get_or_create_trait_type("foo", 0)
        self.assertEqual(tt2.id, tt1.id)
        self.assertEqual(tt2.desc, tt1.desc)
        self.assertEqual(tt2.data_type, tt1.data_type)

    def test_new_trait_type(self):
        tt1 = self.conn._get_or_create_trait_type("foo", 0)
        self.assertTrue(tt1.id >= 0)
        tt2 = self.conn._get_or_create_trait_type("blah", 0)
        self.assertNotEqual(tt1.id, tt2.id)
        self.assertNotEqual(tt1.desc, tt2.desc)
        # Test the method __repr__ returns a string
        self.assertTrue(repr.repr(tt2))

    def test_trait_different_data_type(self):
        tt1 = self.conn._get_or_create_trait_type("foo", 0)
        self.assertTrue(tt1.id >= 0)
        tt2 = self.conn._get_or_create_trait_type("foo", 1)
        self.assertNotEqual(tt1.id, tt2.id)
        self.assertEqual(tt2.desc, tt1.desc)
        self.assertNotEqual(tt1.data_type, tt2.data_type)
        # Test the method __repr__ returns a string
        self.assertTrue(repr.repr(tt2))


@tests_db.run_with('sqlite')
class EventTypeTest(tests_db.TestBase):
    # EventType is a construct specific to sqlalchemy
    # Not applicable to other drivers.

    def test_event_type_exists(self):
        et1 = self.conn._get_or_create_event_type("foo")
        self.assertTrue(et1.id >= 0)
        et2 = self.conn._get_or_create_event_type("foo")
        self.assertEqual(et2.id, et1.id)
        self.assertEqual(et2.desc, et1.desc)

    def test_event_type_unique(self):
        et1 = self.conn._get_or_create_event_type("foo")
        self.assertTrue(et1.id >= 0)
        et2 = self.conn._get_or_create_event_type("blah")
        self.assertNotEqual(et1.id, et2.id)
        self.assertNotEqual(et1.desc, et2.desc)
        # Test the method __repr__ returns a string
        self.assertTrue(repr.repr(et2))


class MyException(Exception):
    pass


@tests_db.run_with('sqlite')
class EventTest(tests_db.TestBase):
    def test_string_traits(self):
        model = models.Trait("Foo", models.Trait.TEXT_TYPE, "my_text")
        trait = self.conn._make_trait(model, None)
        self.assertEqual(models.Trait.TEXT_TYPE, trait.trait_type.data_type)
        self.assertIsNone(trait.t_float)
        self.assertIsNone(trait.t_int)
        self.assertIsNone(trait.t_datetime)
        self.assertEqual("my_text", trait.t_string)
        self.assertIsNotNone(trait.trait_type.desc)

    def test_int_traits(self):
        model = models.Trait("Foo", models.Trait.INT_TYPE, 100)
        trait = self.conn._make_trait(model, None)
        self.assertEqual(models.Trait.INT_TYPE, trait.trait_type.data_type)
        self.assertIsNone(trait.t_float)
        self.assertIsNone(trait.t_string)
        self.assertIsNone(trait.t_datetime)
        self.assertEqual(100, trait.t_int)
        self.assertIsNotNone(trait.trait_type.desc)

    def test_float_traits(self):
        model = models.Trait("Foo", models.Trait.FLOAT_TYPE, 123.456)
        trait = self.conn._make_trait(model, None)
        self.assertEqual(models.Trait.FLOAT_TYPE, trait.trait_type.data_type)
        self.assertIsNone(trait.t_int)
        self.assertIsNone(trait.t_string)
        self.assertIsNone(trait.t_datetime)
        self.assertEqual(123.456, trait.t_float)
        self.assertIsNotNone(trait.trait_type.desc)

    def test_datetime_traits(self):
        now = datetime.datetime.utcnow()
        model = models.Trait("Foo", models.Trait.DATETIME_TYPE, now)
        trait = self.conn._make_trait(model, None)
        self.assertEqual(models.Trait.DATETIME_TYPE,
                         trait.trait_type.data_type)
        self.assertIsNone(trait.t_int)
        self.assertIsNone(trait.t_string)
        self.assertIsNone(trait.t_float)
        self.assertEqual(now, trait.t_datetime)
        self.assertIsNotNone(trait.trait_type.desc)

    def test_bad_event(self):
        now = datetime.datetime.utcnow()
        m = [models.Event("1", "Foo", now, []),
             models.Event("2", "Zoo", now, [])]

        with mock.patch.object(self.conn, "_record_event") as mock_save:
            mock_save.side_effect = MyException("Boom")
            problem_events = self.conn.record_events(m)
        self.assertEqual(2, len(problem_events))
        for bad, event in problem_events:
            self.assertEqual(bad, models.Event.UNKNOWN_PROBLEM)

    def test_get_none_value_traits(self):
        model = sql_models.Trait(None, None, 5)
        self.assertIsNone(model.get_value())
        self.assertTrue(repr.repr(model))

    def test_event_repr(self):
        ev = sql_models.Event('msg_id', None, False)
        ev.id = 100
        self.assertTrue(repr.repr(ev))


@tests_db.run_with('sqlite')
class RelationshipTest(scenarios.DBTestBase):
    # Note: Do not derive from SQLAlchemyEngineTestBase, since we
    # don't want to automatically inherit all the Meter setup.

    @mock.patch.object(timeutils, 'utcnow')
    def test_clear_metering_data_meta_tables(self, mock_utcnow):
        mock_utcnow.return_value = datetime.datetime(2012, 7, 2, 10, 45)
        self.conn.clear_expired_metering_data(3 * 60)

        session = self.conn._engine_facade.get_session()
        meta_tables = [sql_models.MetaText, sql_models.MetaFloat,
                       sql_models.MetaBigInt, sql_models.MetaBool]
        for table in meta_tables:
            self.assertEqual(0, (session.query(table)
                                 .filter(~table.id.in_(
                                     session.query(sql_models.Sample.id)
                                     .group_by(sql_models.Sample.id))).count()
                                 ))


class CapabilitiesTest(test_base.BaseTestCase):
    # Check the returned capabilities list, which is specific to each DB
    # driver

    def test_capabilities(self):
        expected_capabilities = {
            'meters': {'pagination': False,
                       'query': {'simple': True,
                                 'metadata': True,
                                 'complex': False}},
            'resources': {'pagination': False,
                          'query': {'simple': True,
                                    'metadata': True,
                                    'complex': False}},
            'samples': {'pagination': True,
                        'groupby': True,
                        'query': {'simple': True,
                                  'metadata': True,
                                  'complex': True}},
            'statistics': {'pagination': False,
                           'groupby': True,
                           'query': {'simple': True,
                                     'metadata': True,
                                     'complex': False},
                           'aggregation': {'standard': True,
                                           'selectable': {
                                               'max': True,
                                               'min': True,
                                               'sum': True,
                                               'avg': True,
                                               'count': True,
                                               'stddev': True,
                                               'cardinality': True}}
                           },
            'events': {'query': {'simple': True}}
        }

        actual_capabilities = impl_sqlalchemy.Connection.get_capabilities()
        self.assertEqual(expected_capabilities, actual_capabilities)

    def test_alarm_capabilities(self):
        expected_capabilities = {
            'alarms': {'query': {'simple': True,
                                 'complex': True},
                       'history': {'query': {'simple': True,
                                             'complex': True}}},
        }

        actual_capabilities = impl_sqla_alarm.Connection.get_capabilities()
        self.assertEqual(expected_capabilities, actual_capabilities)

    def test_storage_capabilities(self):
        expected_capabilities = {
            'storage': {'production_ready': True},
        }
        actual_capabilities = (impl_sqlalchemy.
                               Connection.get_storage_capabilities())
        self.assertEqual(expected_capabilities, actual_capabilities)
