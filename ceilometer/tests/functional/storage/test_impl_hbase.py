#
# Copyright 2012, 2013 Dell Inc.
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
import mock


try:
    import happybase   # noqa
except ImportError:
    import testtools.testcase
    raise testtools.testcase.TestSkipped("happybase is needed")

from ceilometer.storage import impl_hbase as hbase
from ceilometer.tests import base as test_base
from ceilometer.tests import db as tests_db


class ConnectionTest(tests_db.TestBase):

    @tests_db.run_with('hbase')
    def test_hbase_connection(self):

        class TestConn(object):
            def __init__(self, host, port):
                self.netloc = '%s:%s' % (host, port)

            def open(self):
                pass

        def get_connection_pool(conf):
            return TestConn(conf['host'], conf['port'])

        with mock.patch.object(hbase.Connection, '_get_connection_pool',
                               side_effect=get_connection_pool):
            conn = hbase.Connection(self.CONF, 'hbase://test_hbase:9090')
        self.assertIsInstance(conn.conn_pool, TestConn)


class CapabilitiesTest(test_base.BaseTestCase):
    # Check the returned capabilities list, which is specific to each DB
    # driver

    def test_capabilities(self):
        expected_capabilities = {
            'meters': {'query': {'simple': True,
                                 'metadata': True}},
            'resources': {'query': {'simple': True,
                                    'metadata': True}},
            'samples': {'query': {'simple': True,
                                  'metadata': True,
                                  'complex': False}},
            'statistics': {'groupby': False,
                           'query': {'simple': True,
                                     'metadata': True},
                           'aggregation': {'standard': True,
                                           'selectable': {
                                               'max': False,
                                               'min': False,
                                               'sum': False,
                                               'avg': False,
                                               'count': False,
                                               'stddev': False,
                                               'cardinality': False}}
                           },
        }

        actual_capabilities = hbase.Connection.get_capabilities()
        self.assertEqual(expected_capabilities, actual_capabilities)

    def test_storage_capabilities(self):
        expected_capabilities = {
            'storage': {'production_ready': True},
        }
        actual_capabilities = hbase.Connection.get_storage_capabilities()
        self.assertEqual(expected_capabilities, actual_capabilities)
