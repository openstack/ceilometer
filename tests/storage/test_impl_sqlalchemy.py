# -*- encoding: utf-8 -*-
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
from mock import patch

from ceilometer.storage import models
from ceilometer.storage.sqlalchemy.models import table_args
from ceilometer import utils
from ceilometer.tests import db as tests_db


class EventTestBase(tests_db.TestBase):
    # Note: Do not derive from SQLAlchemyEngineTestBase, since we
    # don't want to automatically inherit all the Meter setup.
    database_connection = 'sqlite://'


class UniqueNameTest(EventTestBase):
    # UniqueName is a construct specific to sqlalchemy.
    # Not applicable to other drivers.

    def test_unique_exists(self):
        u1 = self.conn._get_or_create_unique_name("foo")
        self.assertTrue(u1.id >= 0)
        u2 = self.conn._get_or_create_unique_name("foo")
        self.assertEqual(u1.id, u2.id)
        self.assertEqual(u1.key, u2.key)

    def test_new_unique(self):
        u1 = self.conn._get_or_create_unique_name("foo")
        self.assertTrue(u1.id >= 0)
        u2 = self.conn._get_or_create_unique_name("blah")
        self.assertNotEqual(u1.id, u2.id)
        self.assertNotEqual(u1.key, u2.key)


class MyException(Exception):
    pass


class EventTest(EventTestBase):
    def test_string_traits(self):
        model = models.Trait("Foo", models.Trait.TEXT_TYPE, "my_text")
        trait = self.conn._make_trait(model, None)
        self.assertEqual(trait.t_type, models.Trait.TEXT_TYPE)
        self.assertIsNone(trait.t_float)
        self.assertIsNone(trait.t_int)
        self.assertIsNone(trait.t_datetime)
        self.assertEqual(trait.t_string, "my_text")
        self.assertIsNotNone(trait.name)

    def test_int_traits(self):
        model = models.Trait("Foo", models.Trait.INT_TYPE, 100)
        trait = self.conn._make_trait(model, None)
        self.assertEqual(trait.t_type, models.Trait.INT_TYPE)
        self.assertIsNone(trait.t_float)
        self.assertIsNone(trait.t_string)
        self.assertIsNone(trait.t_datetime)
        self.assertEqual(trait.t_int, 100)
        self.assertIsNotNone(trait.name)

    def test_float_traits(self):
        model = models.Trait("Foo", models.Trait.FLOAT_TYPE, 123.456)
        trait = self.conn._make_trait(model, None)
        self.assertEqual(trait.t_type, models.Trait.FLOAT_TYPE)
        self.assertIsNone(trait.t_int)
        self.assertIsNone(trait.t_string)
        self.assertIsNone(trait.t_datetime)
        self.assertEqual(trait.t_float, 123.456)
        self.assertIsNotNone(trait.name)

    def test_datetime_traits(self):
        now = datetime.datetime.utcnow()
        model = models.Trait("Foo", models.Trait.DATETIME_TYPE, now)
        trait = self.conn._make_trait(model, None)
        self.assertEqual(trait.t_type, models.Trait.DATETIME_TYPE)
        self.assertIsNone(trait.t_int)
        self.assertIsNone(trait.t_string)
        self.assertIsNone(trait.t_float)
        self.assertEqual(trait.t_datetime, utils.dt_to_decimal(now))
        self.assertIsNotNone(trait.name)

    def test_bad_event(self):
        now = datetime.datetime.utcnow()
        m = [models.Event("1", "Foo", now, []),
             models.Event("2", "Zoo", now, [])]

        with patch.object(self.conn, "_record_event") as mock_save:
            mock_save.side_effect = MyException("Boom")
            problem_events = self.conn.record_events(m)
        self.assertEquals(2, len(problem_events))
        for bad, event in problem_events:
            self.assertEquals(models.Event.UNKNOWN_PROBLEM, bad)


class ModelTest(tests_db.TestBase):
    database_connection = 'mysql://localhost'

    def test_model_table_args(self):
        self.assertIsNotNone(table_args())
