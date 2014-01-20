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
import repr

from mock import patch

from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common import timeutils
from ceilometer.storage import models
from ceilometer.storage.sqlalchemy import models as sql_models
from ceilometer.tests import base as tests_base
from ceilometer.tests import db as tests_db
from ceilometer.tests.storage import test_storage_scenarios as scenarios


class EventTestBase(tests_db.TestBase):
    # Note: Do not derive from SQLAlchemyEngineTestBase, since we
    # don't want to automatically inherit all the Meter setup.
    database_connection = 'sqlite://'


class CeilometerBaseTest(EventTestBase):
    def test_ceilometer_base(self):
        base = sql_models.CeilometerBase()
        base['key'] = 'value'
        self.assertEqual(base['key'], 'value')


class TraitTypeTest(EventTestBase):
    # TraitType is a construct specific to sqlalchemy.
    # Not applicable to other drivers.

    def test_trait_type_exists(self):
        tt1 = self.conn._get_or_create_trait_type("foo", 0)
        self.assertTrue(tt1.id >= 0)
        tt2 = self.conn._get_or_create_trait_type("foo", 0)
        self.assertEqual(tt1.id, tt2.id)
        self.assertEqual(tt1.desc, tt2.desc)
        self.assertEqual(tt1.data_type, tt2.data_type)

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
        self.assertEqual(tt1.desc, tt2.desc)
        self.assertNotEqual(tt1.data_type, tt2.data_type)
        # Test the method __repr__ returns a string
        self.assertTrue(repr.repr(tt2))


class EventTypeTest(EventTestBase):
    # EventType is a construct specific to sqlalchemy
    # Not applicable to other drivers.

    def test_event_type_exists(self):
        et1 = self.conn._get_or_create_event_type("foo")
        self.assertTrue(et1.id >= 0)
        et2 = self.conn._get_or_create_event_type("foo")
        self.assertEqual(et1.id, et2.id)
        self.assertEqual(et1.desc, et2.desc)

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


class EventTest(EventTestBase):
    def test_string_traits(self):
        model = models.Trait("Foo", models.Trait.TEXT_TYPE, "my_text")
        trait = self.conn._make_trait(model, None)
        self.assertEqual(trait.trait_type.data_type, models.Trait.TEXT_TYPE)
        self.assertIsNone(trait.t_float)
        self.assertIsNone(trait.t_int)
        self.assertIsNone(trait.t_datetime)
        self.assertEqual(trait.t_string, "my_text")
        self.assertIsNotNone(trait.trait_type.desc)

    def test_int_traits(self):
        model = models.Trait("Foo", models.Trait.INT_TYPE, 100)
        trait = self.conn._make_trait(model, None)
        self.assertEqual(trait.trait_type.data_type, models.Trait.INT_TYPE)
        self.assertIsNone(trait.t_float)
        self.assertIsNone(trait.t_string)
        self.assertIsNone(trait.t_datetime)
        self.assertEqual(trait.t_int, 100)
        self.assertIsNotNone(trait.trait_type.desc)

    def test_float_traits(self):
        model = models.Trait("Foo", models.Trait.FLOAT_TYPE, 123.456)
        trait = self.conn._make_trait(model, None)
        self.assertEqual(trait.trait_type.data_type, models.Trait.FLOAT_TYPE)
        self.assertIsNone(trait.t_int)
        self.assertIsNone(trait.t_string)
        self.assertIsNone(trait.t_datetime)
        self.assertEqual(trait.t_float, 123.456)
        self.assertIsNotNone(trait.trait_type.desc)

    def test_datetime_traits(self):
        now = datetime.datetime.utcnow()
        model = models.Trait("Foo", models.Trait.DATETIME_TYPE, now)
        trait = self.conn._make_trait(model, None)
        self.assertEqual(trait.trait_type.data_type,
                         models.Trait.DATETIME_TYPE)
        self.assertIsNone(trait.t_int)
        self.assertIsNone(trait.t_string)
        self.assertIsNone(trait.t_float)
        self.assertEqual(trait.t_datetime, now)
        self.assertIsNotNone(trait.trait_type.desc)

    def test_bad_event(self):
        now = datetime.datetime.utcnow()
        m = [models.Event("1", "Foo", now, []),
             models.Event("2", "Zoo", now, [])]

        with patch.object(self.conn, "_record_event") as mock_save:
            mock_save.side_effect = MyException("Boom")
            problem_events = self.conn.record_events(m)
        self.assertEqual(2, len(problem_events))
        for bad, event in problem_events:
            self.assertEqual(models.Event.UNKNOWN_PROBLEM, bad)

    def test_get_none_value_traits(self):
        model = sql_models.Trait(None, None, 5)
        self.assertIsNone(model.get_value())
        self.assertTrue(repr.repr(model))

    def test_event_repr(self):
        ev = sql_models.Event('msg_id', None, False)
        ev.id = 100
        self.assertTrue(repr.repr(ev))


class ModelTest(tests_base.BaseTestCase):
    database_connection = 'mysql://localhost'

    def test_model_table_args(self):
        self.CONF = self.useFixture(config.Config()).conf
        self.CONF.set_override('connection', self.database_connection,
                               group='database')
        self.assertIsNotNone(sql_models.table_args())


class RelationshipTest(scenarios.DBTestBase):
    # Note: Do not derive from SQLAlchemyEngineTestBase, since we
    # don't want to automatically inherit all the Meter setup.
    database_connection = 'sqlite://'

    def test_clear_metering_data_meta_tables(self):
        timeutils.utcnow.override_time = datetime.datetime(2012, 7, 2, 10, 45)
        self.conn.clear_expired_metering_data(3 * 60)

        session = self.conn._get_db_session()
        meta_tables = [sql_models.MetaText, sql_models.MetaFloat,
                       sql_models.MetaBigInt, sql_models.MetaBool]
        for table in meta_tables:
            self.assertEqual(session.query(table)
                .filter(~table.id.in_(
                    session.query(sql_models.Meter.id)
                        .group_by(sql_models.Meter.id)
                        )).count(), 0)

    def test_clear_metering_data_associations(self):
        timeutils.utcnow.override_time = datetime.datetime(2012, 7, 2, 10, 45)
        self.conn.clear_expired_metering_data(3 * 60)

        session = self.conn._get_db_session()
        self.assertEqual(session.query(sql_models.sourceassoc)
            .filter(~sql_models.sourceassoc.c.meter_id.in_(
                session.query(sql_models.Meter.id)
                    .group_by(sql_models.Meter.id)
                    )).count(), 0)
        self.assertEqual(session.query(sql_models.sourceassoc)
            .filter(~sql_models.sourceassoc.c.project_id.in_(
                session.query(sql_models.Project.id)
                    .group_by(sql_models.Project.id)
                    )).count(), 0)
        self.assertEqual(session.query(sql_models.sourceassoc)
            .filter(~sql_models.sourceassoc.c.user_id.in_(
                session.query(sql_models.User.id)
                    .group_by(sql_models.User.id)
                    )).count(), 0)
