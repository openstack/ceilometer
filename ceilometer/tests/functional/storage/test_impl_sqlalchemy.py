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
import warnings

import mock
from oslo_db import exception
from oslo_utils import timeutils
from six.moves import reprlib

from ceilometer.event.storage import impl_sqlalchemy as impl_sqla_event
from ceilometer.event.storage import models
from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.storage import impl_sqlalchemy
from ceilometer.storage.sqlalchemy import models as sql_models
from ceilometer.tests import base as test_base
from ceilometer.tests import db as tests_db
from ceilometer.tests.functional.storage \
    import test_storage_scenarios as scenarios


@tests_db.run_with('sqlite', 'mysql', 'pgsql')
class CeilometerBaseTest(tests_db.TestBase):

    def test_ceilometer_base(self):
        base = sql_models.CeilometerBase()
        base['key'] = 'value'
        self.assertEqual('value', base['key'])


@tests_db.run_with('sqlite')
class EngineFacadeTest(tests_db.TestBase):

    @mock.patch.object(warnings, 'warn')
    def test_no_not_supported_warning(self, mocked):
        impl_sqlalchemy.Connection('sqlite://')
        impl_sqla_event.Connection('sqlite://')
        self.assertNotIn(mock.call(mock.ANY, exception.NotSupportedWarning),
                         mocked.call_args_list)


@tests_db.run_with('sqlite', 'mysql', 'pgsql')
class EventTypeTest(tests_db.TestBase):
    # EventType is a construct specific to sqlalchemy
    # Not applicable to other drivers.

    def test_event_type_exists(self):
        et1 = self.event_conn._get_or_create_event_type("foo")
        self.assertTrue(et1.id >= 0)
        et2 = self.event_conn._get_or_create_event_type("foo")
        self.assertEqual(et2.id, et1.id)
        self.assertEqual(et2.desc, et1.desc)

    def test_event_type_unique(self):
        et1 = self.event_conn._get_or_create_event_type("foo")
        self.assertTrue(et1.id >= 0)
        et2 = self.event_conn._get_or_create_event_type("blah")
        self.assertNotEqual(et1.id, et2.id)
        self.assertNotEqual(et1.desc, et2.desc)
        # Test the method __repr__ returns a string
        self.assertTrue(reprlib.repr(et2))


@tests_db.run_with('sqlite', 'mysql', 'pgsql')
class EventTest(tests_db.TestBase):
    def _verify_data(self, trait, trait_table):
        now = datetime.datetime.utcnow()
        ev = models.Event('1', 'name', now, [trait], {})
        self.event_conn.record_events([ev])
        session = self.event_conn._engine_facade.get_session()
        t_tables = [sql_models.TraitText, sql_models.TraitFloat,
                    sql_models.TraitInt, sql_models.TraitDatetime]
        for table in t_tables:
            if table == trait_table:
                self.assertEqual(1, session.query(table).count())
            else:
                self.assertEqual(0, session.query(table).count())

    def test_string_traits(self):
        model = models.Trait("Foo", models.Trait.TEXT_TYPE, "my_text")
        self._verify_data(model, sql_models.TraitText)

    def test_int_traits(self):
        model = models.Trait("Foo", models.Trait.INT_TYPE, 100)
        self._verify_data(model, sql_models.TraitInt)

    def test_float_traits(self):
        model = models.Trait("Foo", models.Trait.FLOAT_TYPE, 123.456)
        self._verify_data(model, sql_models.TraitFloat)

    def test_datetime_traits(self):
        now = datetime.datetime.utcnow()
        model = models.Trait("Foo", models.Trait.DATETIME_TYPE, now)
        self._verify_data(model, sql_models.TraitDatetime)

    def test_event_repr(self):
        ev = sql_models.Event('msg_id', None, False, {})
        ev.id = 100
        self.assertTrue(reprlib.repr(ev))


@tests_db.run_with('sqlite', 'mysql', 'pgsql')
class RelationshipTest(scenarios.DBTestBase):
    # Note: Do not derive from SQLAlchemyEngineTestBase, since we
    # don't want to automatically inherit all the Meter setup.

    @mock.patch.object(timeutils, 'utcnow')
    def test_clear_metering_data_meta_tables(self, mock_utcnow):
        mock_utcnow.return_value = datetime.datetime(2012, 7, 2, 10, 45)
        self.conn.clear_expired_metering_data(3 * 60)

        session = self.conn._engine_facade.get_session()
        self.assertEqual(5, session.query(sql_models.Sample).count())

        resource_ids = (session.query(sql_models.Resource.internal_id)
                        .group_by(sql_models.Resource.internal_id))
        meta_tables = [sql_models.MetaText, sql_models.MetaFloat,
                       sql_models.MetaBigInt, sql_models.MetaBool]
        s = set()
        for table in meta_tables:
            self.assertEqual(0, (session.query(table)
                                 .filter(~table.id.in_(resource_ids)).count()
                                 ))
            s.update(session.query(table.id).all())
        self.assertEqual(set(resource_ids.all()), s)


class CapabilitiesTest(test_base.BaseTestCase):
    # Check the returned capabilities list, which is specific to each DB
    # driver

    def test_capabilities(self):
        expected_capabilities = {
            'meters': {'query': {'simple': True,
                                 'metadata': True,
                                 'complex': False}},
            'resources': {'query': {'simple': True,
                                    'metadata': True,
                                    'complex': False}},
            'samples': {'query': {'simple': True,
                                  'metadata': True,
                                  'complex': True}},
            'statistics': {'groupby': True,
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
        }

        actual_capabilities = impl_sqlalchemy.Connection.get_capabilities()
        self.assertEqual(expected_capabilities, actual_capabilities)

    def test_event_capabilities(self):
        expected_capabilities = {
            'events': {'query': {'simple': True}},
        }
        actual_capabilities = impl_sqla_event.Connection.get_capabilities()
        self.assertEqual(expected_capabilities, actual_capabilities)

    def test_storage_capabilities(self):
        expected_capabilities = {
            'storage': {'production_ready': True},
        }
        actual_capabilities = (impl_sqlalchemy.
                               Connection.get_storage_capabilities())
        self.assertEqual(expected_capabilities, actual_capabilities)


@tests_db.run_with('sqlite', 'mysql', 'pgsql')
class FilterQueryTestForMeters(scenarios.DBTestBase):
    def prepare_data(self):
            self.counters = []
            c = sample.Sample(
                'volume.size',
                'gauge',
                'GiB',
                5,
                user_id=None,
                project_id=None,
                resource_id='fake_id',
                timestamp=datetime.datetime(2012, 9, 25, 10, 30),
                resource_metadata={'display_name': 'test-volume',
                                   'tag': 'self.counter',
                                   },
                source='test',
            )

            self.counters.append(c)
            msg = utils.meter_message_from_counter(
                c,
                secret='not-so-secret')
            self.conn.record_metering_data(msg)

    def test_get_meters_by_user(self):
        meters = list(self.conn.get_meters(user='None'))
        self.assertEqual(1, len(meters))

    def test_get_meters_by_project(self):
        meters = list(self.conn.get_meters(project='None'))
        self.assertEqual(1, len(meters))
