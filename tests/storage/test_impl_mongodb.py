# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Tests for ceilometer/storage/impl_mongodb.py

.. note::

  (dhellmann) These tests have some dependencies which cannot be
  installed in the CI environment right now.

  Ming is necessary to provide the Mongo-in-memory implementation for
  of MongoDB. The original source for Ming is at
  http://sourceforge.net/project/merciless but there does not seem to
  be a way to point to a "zipball" of the latest HEAD there, and we
  need features present only in that version. I forked the project to
  github to make it easier to install, and put the URL into the
  test-requires file. Then I ended up making some changes to it so it
  would be compatible with PyMongo's API.

    https://github.com/dreamhost/Ming/zipball/master#egg=Ming

  In order to run the tests that use map-reduce with MIM, some
  additional system-level packages are required::

    apt-get install nspr-config
    apt-get install libnspr4-dev
    apt-get install pkg-config
    pip install python-spidermonkey

  To run the tests *without* mim, set the environment variable
  CEILOMETER_TEST_LIVE=1 before running tox.

"""

import mox

from tests.storage import base
from ceilometer.storage.impl_test import TestConnection
from ceilometer.tests.db import require_map_reduce


class MongoDBEngine(base.DBEngineBase):

    DBNAME = 'testdb'

    def tearDown(self):
        self.conn.drop_database(self.DBNAME)
        super(MongoDBEngine, self).tearDown()

    def get_connection(self):
        conf = mox.Mox().CreateMockAnything()
        conf.database_connection = 'mongodb://localhost/%s' % self.DBNAME
        self.conn = TestConnection(conf)
        self.db = self.conn.conn[self.DBNAME]
        return self.conn

    def clean_up(self):
        self.conn.drop_database(self.DBNAME)

    def get_sources_by_project_id(self, id):
        project = self.db.project.find_one({'_id': id})
        return list(project['source'])

    def get_sources_by_user_id(self, id):
        user = self.db.user.find_one({'_id': id})
        return list(user['source'])


class MongoDBEngineTestBase(base.DBTestBase):

    def get_engine(cls):
        return MongoDBEngine()


class IndexTest(MongoDBEngineTestBase):

    def test_indexes_exist(self):
        # ensure_index returns none if index already exists
        assert self.engine is not None
        assert not self.engine.db.resource.ensure_index('foo',
                                                        name='resource_idx')
        assert not self.engine.db.meter.ensure_index('foo',
                                                     name='meter_idx')


class UserTest(base.UserTest, MongoDBEngineTestBase):
    pass


class ProjectTest(base.ProjectTest, MongoDBEngineTestBase):
    pass


class ResourceTest(base.ResourceTest, MongoDBEngineTestBase):
    pass


class MeterTest(base.MeterTest, MongoDBEngineTestBase):
    pass


class RawEventTest(base.RawEventTest, MongoDBEngineTestBase):
    pass


class SumTest(base.SumTest, MongoDBEngineTestBase):

    def setUp(self):
        super(SumTest, self).setUp()
        require_map_reduce(self.conn)


class TestGetEventInterval(base.TestGetEventInterval, MongoDBEngineTestBase):

    def setUp(self):
        super(TestGetEventInterval, self).setUp()
        require_map_reduce(self.conn)


class MaxProjectTest(base.MaxProjectTest, MongoDBEngineTestBase):

    def setUp(self):
        super(MaxProjectTest, self).setUp()
        require_map_reduce(self.conn)


class MaxResourceTest(base.MaxResourceTest, MongoDBEngineTestBase):

    def setUp(self):
        super(MaxResourceTest, self).setUp()
        require_map_reduce(self.conn)


class StatisticsTest(base.StatisticsTest, MongoDBEngineTestBase):

    def setUp(self):
        super(StatisticsTest, self).setUp()
        require_map_reduce(self.conn)
