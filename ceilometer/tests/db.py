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

import logging
import os

from ming import mim

import mock

from nose.plugins import skip

from ceilometer.storage import impl_mongodb
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
        return

    def tearDown(self):
        self.conn.drop_database(self.DBNAME)


class TestConnection(impl_mongodb.Connection):

    _mim_instance = None
    FORCE_MONGO = bool(int(os.environ.get('CEILOMETER_TEST_LIVE', 0)))

    def drop_database(self, database):
        if TestConnection._mim_instance is not None:
            # Don't want to use drop_database() because we
            # may end up running out of spidermonkey instances.
            # http://davisp.lighthouseapp.com/projects/26898/tickets/22
            self.conn[database].clear()
        else:
            self.conn.drop_database(database)

    def _get_connection(self, conf):
        # Use a real MongoDB server if we can connect, but fall back
        # to a Mongo-in-memory connection if we cannot.
        if self.FORCE_MONGO:
            try:
                return super(TestConnection, self)._get_connection(conf)
            except:
                LOG.debug('Unable to connect to mongodb')
                raise
        else:
            LOG.debug('Using MIM for test connection')

            # MIM will die if we have too many connections, so use a
            # Singleton
            if TestConnection._mim_instance is None:
                LOG.debug('Creating a new MIM Connection object')
                TestConnection._mim_instance = mim.Connection()
            return TestConnection._mim_instance


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
