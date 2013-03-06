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

from ming import mim
from nose.plugins import skip
from oslo.config import cfg

from ceilometer import storage
from ceilometer.tests import base as test_base


class BaseException(Exception):
    """A base exception for avoiding false positives."""


class TestBase(test_base.TestCase):

    # Default tests use test:// (MIM)
    database_connection = 'test://'

    def setUp(self):
        super(TestBase, self).setUp()
        cfg.CONF.database_connection = self.database_connection
        self.conn = storage.get_connection(cfg.CONF)
        self.conn.upgrade()
        self.conn.clear()


def require_map_reduce(conn):
    """Raises SkipTest if the connection is using mim.
    """
    # NOTE(dhellmann): mim requires spidermonkey to implement the
    # map-reduce functions, so if we can't import it then just
    # skip these tests unless we aren't using mim.
    try:
        import spidermonkey
    except BaseException:
        if isinstance(conn.conn, mim.Connection):
            raise skip.SkipTest('requires spidermonkey')
