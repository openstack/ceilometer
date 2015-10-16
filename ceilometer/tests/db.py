#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 eNovance
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

"""Base classes for API tests."""
import os
import uuid
import warnings

import fixtures
import mock
from oslo_config import fixture as fixture_config
from oslotest import mockpatch
import six
from six.moves.urllib import parse as urlparse
import sqlalchemy
import testscenarios.testcase
from testtools import testcase

from ceilometer import storage
from ceilometer.tests import base as test_base
try:
    from ceilometer.tests import mocks
except ImportError:
    mocks = None   # happybase module is not Python 3 compatible yet


class MongoDbManager(fixtures.Fixture):

    def __init__(self, url):
        self._url = url

    def setUp(self):
        super(MongoDbManager, self).setUp()
        with warnings.catch_warnings():
            warnings.filterwarnings(
                action='ignore',
                message='.*you must provide a username and password.*')
            try:
                self.connection = storage.get_connection(
                    self.url, 'ceilometer.metering.storage')
                self.alarm_connection = storage.get_connection(
                    self.url, 'ceilometer.alarm.storage')
                self.event_connection = storage.get_connection(
                    self.url, 'ceilometer.event.storage')
            except storage.StorageBadVersion as e:
                raise testcase.TestSkipped(six.text_type(e))

    @property
    def url(self):
        return '%(url)s_%(db)s' % {
            'url': self._url,
            'db': uuid.uuid4().hex
        }


class SQLManager(fixtures.Fixture):
    def setUp(self):
        super(SQLManager, self).setUp()
        self.connection = storage.get_connection(
            self.url, 'ceilometer.metering.storage')
        self.alarm_connection = storage.get_connection(
            self.url, 'ceilometer.alarm.storage')
        self.event_connection = storage.get_connection(
            self.url, 'ceilometer.event.storage')

    @property
    def url(self):
        return self._url.replace('template1', self._db_name)


class PgSQLManager(SQLManager):

    def __init__(self, url):
        self._url = url
        self._db_name = 'ceilometer_%s' % uuid.uuid4().hex
        self._engine = sqlalchemy.create_engine(self._url)
        self._conn = self._engine.connect()
        self._conn.connection.set_isolation_level(0)
        self._conn.execute(
            'CREATE DATABASE %s WITH TEMPLATE template0;' % self._db_name)
        self._conn.connection.set_isolation_level(1)
        self._conn.close()
        self._engine.dispose()


class MySQLManager(SQLManager):

    def __init__(self, url):
        self._url = url
        self._db_name = 'ceilometer_%s' % uuid.uuid4().hex
        self._engine = sqlalchemy.create_engine(
            self._url.replace('template1', ''))
        self._conn = self._engine.connect()
        self._conn.execute('CREATE DATABASE %s;' % self._db_name)
        self._conn.close()
        self._engine.dispose()


class ElasticSearchManager(fixtures.Fixture):
    def __init__(self, url):
        self.url = url

    def setUp(self):
        super(ElasticSearchManager, self).setUp()
        self.connection = storage.get_connection(
            'sqlite://', 'ceilometer.metering.storage')
        self.alarm_connection = storage.get_connection(
            'sqlite://', 'ceilometer.alarm.storage')
        self.event_connection = storage.get_connection(
            self.url, 'ceilometer.event.storage')
        # prefix each test with unique index name
        self.event_connection.index_name = 'events_%s' % uuid.uuid4().hex
        # force index on write so data is queryable right away
        self.event_connection._refresh_on_write = True


class HBaseManager(fixtures.Fixture):
    def __init__(self, url):
        self._url = url

    def setUp(self):
        super(HBaseManager, self).setUp()
        self.connection = storage.get_connection(
            self.url, 'ceilometer.metering.storage')
        self.alarm_connection = storage.get_connection(
            self.url, 'ceilometer.alarm.storage')
        self.event_connection = storage.get_connection(
            self.url, 'ceilometer.event.storage')
        # Unique prefix for each test to keep data is distinguished because
        # all test data is stored in one table
        data_prefix = str(uuid.uuid4().hex)

        def table(conn, name):
            return mocks.MockHBaseTable(name, conn, data_prefix)

        # Mock only real HBase connection, MConnection "table" method
        # stays origin.
        mock.patch('happybase.Connection.table', new=table).start()
        # We shouldn't delete data and tables after each test,
        # because it last for too long.
        # All tests tables will be deleted in setup-test-env.sh
        mock.patch("happybase.Connection.disable_table",
                   new=mock.MagicMock()).start()
        mock.patch("happybase.Connection.delete_table",
                   new=mock.MagicMock()).start()
        mock.patch("happybase.Connection.create_table",
                   new=mock.MagicMock()).start()

    @property
    def url(self):
        return '%s?table_prefix=%s' % (
            self._url,
            os.getenv("CEILOMETER_TEST_HBASE_TABLE_PREFIX", "test")
        )


class SQLiteManager(fixtures.Fixture):

    def __init__(self, url):
        self.url = url

    def setUp(self):
        super(SQLiteManager, self).setUp()
        self.connection = storage.get_connection(
            self.url, 'ceilometer.metering.storage')
        self.alarm_connection = storage.get_connection(
            self.url, 'ceilometer.alarm.storage')
        self.event_connection = storage.get_connection(
            self.url, 'ceilometer.event.storage')


class TestBase(testscenarios.testcase.WithScenarios, test_base.BaseTestCase):

    DRIVER_MANAGERS = {
        'mongodb': MongoDbManager,
        'mysql': MySQLManager,
        'mysql+pymysql': MySQLManager,
        'postgresql': PgSQLManager,
        'db2': MongoDbManager,
        'sqlite': SQLiteManager,
        'es': ElasticSearchManager,
    }
    if mocks is not None:
        DRIVER_MANAGERS['hbase'] = HBaseManager

    db_url = 'sqlite://'  # NOTE(Alexei_987) Set default db url

    def setUp(self):
        super(TestBase, self).setUp()
        engine = urlparse.urlparse(self.db_url).scheme

        # NOTE(Alexei_987) Shortcut to skip expensive db setUp
        test_method = self._get_test_method()
        if (hasattr(test_method, '_run_with')
                and engine not in test_method._run_with):
            raise testcase.TestSkipped(
                'Test is not applicable for %s' % engine)

        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.CONF([], project='ceilometer', validate_default_values=True)

        try:
            self.db_manager = self._get_driver_manager(engine)(self.db_url)
        except ValueError as exc:
            self.skipTest("missing driver manager: %s" % exc)
        self.useFixture(self.db_manager)

        self.conn = self.db_manager.connection
        self.conn.upgrade()

        self.alarm_conn = self.db_manager.alarm_connection
        self.alarm_conn.upgrade()

        self.event_conn = self.db_manager.event_connection
        self.event_conn.upgrade()

        self.useFixture(mockpatch.Patch('ceilometer.storage.get_connection',
                                        side_effect=self._get_connection))

        # Set a default location for the pipeline config file so the
        # tests work even if ceilometer is not installed globally on
        # the system.
        self.CONF.import_opt('pipeline_cfg_file', 'ceilometer.pipeline')
        self.CONF.set_override(
            'pipeline_cfg_file',
            self.path_get('etc/ceilometer/pipeline.yaml')
        )

    def tearDown(self):
        self.event_conn.clear()
        self.event_conn = None
        self.alarm_conn.clear()
        self.alarm_conn = None
        self.conn.clear()
        self.conn = None
        super(TestBase, self).tearDown()

    def _get_connection(self, url, namespace):
        if namespace == "ceilometer.alarm.storage":
            return self.alarm_conn
        elif namespace == "ceilometer.event.storage":
            return self.event_conn
        return self.conn

    def _get_driver_manager(self, engine):
        manager = self.DRIVER_MANAGERS.get(engine)
        if not manager:
            raise ValueError('No manager available for %s' % engine)
        return manager


def run_with(*drivers):
    """Used to mark tests that are only applicable for certain db driver.

    Skips test if driver is not available.
    """
    def decorator(test):
        if isinstance(test, type) and issubclass(test, TestBase):
            # Decorate all test methods
            for attr in dir(test):
                value = getattr(test, attr)
                if callable(value) and attr.startswith('test_'):
                    if six.PY3:
                        value._run_with = drivers
                    else:
                        value.__func__._run_with = drivers
        else:
            test._run_with = drivers
        return test
    return decorator


@six.add_metaclass(test_base.SkipNotImplementedMeta)
class MixinTestsWithBackendScenarios(object):

    scenarios = [
        ('sqlite', {'db_url': 'sqlite://'}),
    ]

    for db in ('MONGODB', 'MYSQL', 'PGSQL', 'HBASE', 'DB2', 'ES'):
        if os.environ.get('CEILOMETER_TEST_%s_URL' % db):
            scenarios.append(
                (db.lower(), {'db_url': os.environ.get(
                    'CEILOMETER_TEST_%s_URL' % db)}))

    scenarios_db = [db for db, _ in scenarios]

    # Insert default value for hbase test
    if 'hbase' not in scenarios_db:
        scenarios.append(
            ('hbase', {'db_url': 'hbase://__test__'}))

    # Insert default value for db2 test
    if 'mongodb' in scenarios_db and 'db2' not in scenarios_db:
        scenarios.append(
            ('db2', {'db_url': os.environ.get('CEILOMETER_TEST_MONGODB_URL',
                                              '').replace('mongodb://',
                                                          'db2://')}))
