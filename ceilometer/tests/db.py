#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 eNovance
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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

"""Base classes for API tests."""
import fixtures
import os
import uuid
import warnings

import mock
from oslo.config import fixture as fixture_config
from oslotest import mockpatch
import six
from six.moves.urllib import parse as urlparse
import testscenarios.testcase
from testtools import testcase

from ceilometer import storage
from ceilometer.tests import base as test_base
from ceilometer.tests import mocks


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
            except storage.StorageBadVersion as e:
                raise testcase.TestSkipped(six.text_type(e))

    @property
    def url(self):
        return '%(url)s_%(db)s' % {
            'url': self._url,
            'db': uuid.uuid4().hex
        }


class HBaseManager(fixtures.Fixture):
    def __init__(self, url):
        self._url = url

    def setUp(self):
        super(HBaseManager, self).setUp()
        self.connection = storage.get_connection(
            self.url, 'ceilometer.metering.storage')
        self.alarm_connection = storage.get_connection(
            self.url, 'ceilometer.alarm.storage')
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


class TestBase(testscenarios.testcase.WithScenarios, test_base.BaseTestCase):

    DRIVER_MANAGERS = {
        'mongodb': MongoDbManager,
        'db2': MongoDbManager,
        'sqlite': SQLiteManager,
        'hbase': HBaseManager,
    }

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
        self.CONF([], project='ceilometer')

        self.db_manager = self._get_driver_manager(engine)(self.db_url)
        self.useFixture(self.db_manager)

        self.conn = self.db_manager.connection
        self.conn.upgrade()

        self.alarm_conn = self.db_manager.alarm_connection
        self.alarm_conn.upgrade()

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
        self.alarm_conn.clear()
        self.alarm_conn = None
        self.conn.clear()
        self.conn = None
        super(TestBase, self).tearDown()

    def _get_connection(self, url, namespace):
        if namespace == "ceilometer.alarm.storage":
            return self.alarm_conn
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
                    value.__func__._run_with = drivers
        else:
            test._run_with = drivers
        return test
    return decorator


@six.add_metaclass(test_base.SkipNotImplementedMeta)
class MixinTestsWithBackendScenarios(object):

    scenarios = [
        ('sqlite', {'db_url': 'sqlite://'}),
        ('mongodb', {'db_url': os.environ.get('CEILOMETER_TEST_MONGODB_URL')}),
        ('hbase', {'db_url': os.environ.get('CEILOMETER_TEST_HBASE_URL',
                                            'hbase://__test__')}),
        ('db2', {'db_url': (os.environ.get('CEILOMETER_TEST_DB2_URL') or
                            os.environ.get('CEILOMETER_TEST_MONGODB_URL',
                                           '').replace('mongodb://',
                                                       'db2://'))})
    ]
