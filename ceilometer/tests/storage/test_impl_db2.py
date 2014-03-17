# -*- encoding: utf-8 -*-
#
# Copyright Ericsson AB 2014. All rights reserved
#
# Authors: Ildiko Vancsa <ildiko.vancsa@ericsson.com>
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
  In order to run the tests against another MongoDB server set the
  environment variable CEILOMETER_TEST_DB2_URL to point to a DB2
  server before running the tests.

"""

from ceilometer.tests import db as tests_db


class DB2EngineTestBase(tests_db.TestBase):
    database_connection = tests_db.DB2FakeConnectionUrl()


class CapabilitiesTest(DB2EngineTestBase):
    # Check the returned capabilities list, which is specific to each DB
    # driver

    def test_capabilities(self):
        expected_capabilities = {
            'meters': {'pagination': False,
                       'query': {'simple': True,
                                 'metadata': True,
                                 'complex': False}},
            'resources': {'pagination': False,
                          'query': {'simple': True,
                                    'metadata': True,
                                    'complex': False}},
            'samples': {'pagination': False,
                        'groupby': False,
                        'query': {'simple': True,
                                  'metadata': True,
                                  'complex': True}},
            'statistics': {'pagination': False,
                           'groupby': True,
                           'query': {'simple': True,
                                     'metadata': True,
                                     'complex': False},
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
            'alarms': {'query': {'simple': True,
                                 'complex': True},
                       'history': {'query': {'simple': True,
                                             'complex': False}}},
            'events': {'query': {'simple': False}}
        }

        actual_capabilities = self.conn.get_capabilities()
        self.assertEqual(expected_capabilities, actual_capabilities)
