# -*- encoding: utf-8 -*-
#
# Copyright © 2012, 2013 Dell Inc.
#
# Author: Stas Maksimov <Stanislav_M@dell.com>
# Author: Shengjie Min <Shengjie_Min@dell.com>
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
"""Tests for ceilometer/storage/impl_hbase.py

.. note::
  In order to run the tests against real HBase server set the environment
  variable CEILOMETER_TEST_HBASE_URL to point to that HBase instance before
  running the tests. Make sure the Thrift server is running on that server.

"""
from ceilometer.openstack.common.fixture import moxstubout
from ceilometer.storage.impl_hbase import Connection
from ceilometer.storage.impl_hbase import MConnection
from ceilometer.tests import db as tests_db


class HBaseEngineTestBase(tests_db.TestBase):
    database_connection = 'hbase://__test__'


class ConnectionTest(HBaseEngineTestBase):

    def setUp(self):
        super(ConnectionTest, self).setUp()
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs

    def test_hbase_connection(self):
        self.CONF.database.connection = self.database_connection
        conn = Connection(self.CONF)
        self.assertIsInstance(conn.conn, MConnection)

        class TestConn(object):
            def __init__(self, host, port):
                self.netloc = '%s:%s' % (host, port)

            def open(self):
                pass

        self.CONF.database.connection = 'hbase://test_hbase:9090'
        self.stubs.Set(Connection, '_get_connection',
                       lambda self, x: TestConn(x['host'], x['port']))
        conn = Connection(self.CONF)
        self.assertIsInstance(conn.conn, TestConn)
