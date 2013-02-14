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
"""Base classes for API tests.
"""

from ming import mim

import mock

from nose.plugins import skip

from ceilometer.openstack.common import log as logging
from ceilometer.storage.impl_test import TestConnection
from ceilometer.tests import base as test_base

LOG = logging.getLogger(__name__)


class TestBase(test_base.TestCase):

    DBNAME = 'testdb'

    def setUp(self):
        super(TestBase, self).setUp()
        self.conf = mock.Mock()
        self.conf.metering_storage_engine = 'mongodb'
        self.conf.database_connection = 'mongodb://localhost/%s' % self.DBNAME
        self.conn = TestConnection(self.conf)
        self.conn.drop_database(self.DBNAME)
        self.conn.conn[self.DBNAME]

    def tearDown(self):
        self.conn.drop_database(self.DBNAME)
        super(TestBase, self).tearDown()


def require_map_reduce(conn):
    """Raises SkipTest if the connection is using mim.
    """
    # NOTE(dhellmann): mim requires spidermonkey to implement the
    # map-reduce functions, so if we can't import it then just
    # skip these tests unless we aren't using mim.
    try:
        import spidermonkey
    except:
        if isinstance(conn.conn, mim.Connection):
            raise skip.SkipTest('requires spidermonkey')
