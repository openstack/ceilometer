# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
# Copyright © 2013 eNovance
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

import six
import testscenarios.testcase

from ceilometer.openstack.common.fixture import config
import ceilometer.openstack.common.fixture.mockpatch as oslo_mock
from ceilometer import storage
from ceilometer.tests import base as test_base


class TestBase(testscenarios.testcase.WithScenarios, test_base.BaseTestCase):
    def setUp(self):
        super(TestBase, self).setUp()

        self.useFixture(self.db_manager)

        self.CONF = self.useFixture(config.Config()).conf

        with warnings.catch_warnings():
            warnings.filterwarnings(
                action='ignore',
                message='.*you must provide a username and password.*')
            try:
                self.conn = storage.get_connection(self.db_manager.connection)
            except storage.StorageBadVersion as e:
                self.skipTest(six.text_type(e))
        self.conn.upgrade()

        self.useFixture(oslo_mock.Patch('ceilometer.storage.get_connection',
                                        return_value=self.conn))

        self.CONF([], project='ceilometer')

        # Set a default location for the pipeline config file so the
        # tests work even if ceilometer is not installed globally on
        # the system.
        self.CONF.set_override(
            'pipeline_cfg_file',
            self.path_get('etc/ceilometer/pipeline.yaml')
        )

    def tearDown(self):
        self.conn.clear()
        self.conn = None
        super(TestBase, self).tearDown()


class MongoDbManager(fixtures.Fixture):

    def __init__(self):
        self.url = os.environ.get('CEILOMETER_TEST_MONGODB_URL')
        if not self.url:
            raise RuntimeError(
                "No MongoDB test URL set,"
                "export CEILOMETER_TEST_MONGODB_URL environment variable")

    def setUp(self):
        super(MongoDbManager, self).setUp()
        self.connection = '%(url)s_%(db)s' % {
            'url': self.url,
            'db': uuid.uuid4().hex
        }


class DB2Manager(MongoDbManager):
    def __init__(self):
        self.url = (os.environ.get('CEILOMETER_TEST_DB2_URL') or
                    os.environ.get('CEILOMETER_TEST_MONGODB_URL'))
        if not self.url:
            raise RuntimeError(
                "No DB2 test URL set, "
                "export CEILOMETER_TEST_DB2_URL environment variable")
        else:
            # This is to make sure that the db2 driver is used when
            # CEILOMETER_TEST_DB2_URL was not set
            self.url = self.url.replace('mongodb:', 'db2:', 1)


class HBaseManager(fixtures.Fixture):
    def __init__(self):
        self.url = os.environ.get('CEILOMETER_TEST_HBASE_URL')
        if not self.url:
            self.url = 'hbase://__test__'

    def setUp(self):
        super(HBaseManager, self).setUp()
        self.connection = '%s?table_prefix=%s' % (
            self.url,
            uuid.uuid4().hex)


class SQLiteManager(fixtures.Fixture):

    def setUp(self):
        super(SQLiteManager, self).setUp()
        self.connection = 'sqlite://'


@six.add_metaclass(test_base.SkipNotImplementedMeta)
class MixinTestsWithBackendScenarios(object):

    scenarios = [
        ('sqlite', {'db_manager': SQLiteManager()}),
        ('mongodb', {'db_manager': MongoDbManager()}),
        ('hbase', {'db_manager': HBaseManager()}),
        ('db2', {'db_manager': DB2Manager()})
    ]
