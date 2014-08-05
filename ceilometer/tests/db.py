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

from oslo.config import fixture as fixture_config
from oslotest import mockpatch
import six
from six.moves.urllib import parse as urlparse
import testscenarios.testcase
from testtools import testcase

from ceilometer import storage
from ceilometer.tests import base as test_base


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

    @property
    def url(self):
        return '%s?table_prefix=%s' % (
            self._url,
            uuid.uuid4().hex
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
                            os.environ.get('CEILOMETER_TEST_MONGODB_URL'))})
    ]
