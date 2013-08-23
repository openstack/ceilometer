# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
# Copyright © 2012 IBM Corp
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
#        Tong Li <litong01@us.ibm.com>
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
"""Tests for ceilometer/storage/impl_db2.py

.. note::
  In order to run the tests against another DB2 server set the
  environment variable CEILOMETER_TEST_DB2_URL to point to a DB2
  server before running the tests.

"""

import os
from ceilometer import storage
from ceilometer.storage import models
from ceilometer.tests import db as tests_db
from tests.storage import base


class TestCaseConnectionUrl(tests_db.MongoDBFakeConnectionUrl):

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


class DB2EngineTestBase(base.DBTestBase):
    database_connection = TestCaseConnectionUrl()


class ConnectionTest(DB2EngineTestBase):
    pass


class UserTest(base.UserTest, DB2EngineTestBase):
    pass


class ProjectTest(base.ProjectTest, DB2EngineTestBase):
    pass


class ResourceTest(base.ResourceTest, DB2EngineTestBase):

    def test_get_resources(self):
        msgs_sources = [msg['source'] for msg in self.msgs]
        resources = list(self.conn.get_resources())
        self.assertEqual(len(resources), 9)
        for resource in resources:
            if resource.resource_id != 'resource-id':
                continue
            self.assertEqual(resource.first_sample_timestamp,
                             None)
            self.assertEqual(resource.last_sample_timestamp,
                             None)
            assert resource.resource_id == 'resource-id'
            assert resource.project_id == 'project-id'
            self.assertIn(resource.source, msgs_sources)
            assert resource.user_id == 'user-id'
            assert resource.metadata['display_name'] == 'test-server'
            self.assertIn(models.ResourceMeter('instance', 'cumulative', ''),
                          resource.meter)
            break
        else:
            assert False, 'Never found resource-id'


class MeterTest(base.MeterTest, DB2EngineTestBase):
    pass


class RawSampleTest(base.RawSampleTest, DB2EngineTestBase):
    pass


class StatisticsTest(base.StatisticsTest, DB2EngineTestBase):

    def test_by_user_period_with_timezone(self):
        f = storage.SampleFilter(
            user='user-5',
            meter='volume.size',
            start='2012-09-25T00:28:00-10:00Z'
        )
        try:
            self.conn.get_meter_statistics(f, period=7200)
            got_not_imp = False
        except NotImplementedError:
            got_not_imp = True
        self.assertTrue(got_not_imp)

    def test_by_user_period(self):
        f = storage.SampleFilter(
            user='user-5',
            meter='volume.size',
            start='2012-09-25T10:28:00',
        )
        try:
            self.conn.get_meter_statistics(f, period=7200)
            got_not_imp = False
        except NotImplementedError:
            got_not_imp = True
        self.assertTrue(got_not_imp)

    def test_by_user_period_start_end(self):
        f = storage.SampleFilter(
            user='user-5',
            meter='volume.size',
            start='2012-09-25T10:28:00',
            end='2012-09-25T11:28:00',
        )
        try:
            self.conn.get_meter_statistics(f, period=1800)
            got_not_imp = False
        except NotImplementedError:
            got_not_imp = True
        self.assertTrue(got_not_imp)


class CounterDataTypeTest(base.CounterDataTypeTest, DB2EngineTestBase):
    pass
