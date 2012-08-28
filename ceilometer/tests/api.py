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

import json
import logging
import os
import unittest

import flask
from ming import mim
import mock

from ceilometer.api import v1
from ceilometer.storage import impl_mongodb

LOG = logging.getLogger(__name__)


class Connection(impl_mongodb.Connection):

    def _get_connection(self, conf):
        # Use a real MongoDB server if we can connect, but fall back
        # to a Mongo-in-memory connection if we cannot.
        self.force_mongo = bool(int(os.environ.get('CEILOMETER_TEST_LIVE', 0)))
        if self.force_mongo:
            try:
                return super(Connection, self)._get_connection(conf)
            except:
                LOG.debug('Unable to connect to mongod')
                raise
        else:
            LOG.debug('Unable to connect to mongod, falling back to MIM')
            return mim.Connection()


class TestBase(unittest.TestCase):

    DBNAME = 'testdb'

    def setUp(self):
        super(TestBase, self).setUp()
        self.app = flask.Flask('test')
        self.app.register_blueprint(v1.blueprint)
        self.test_app = self.app.test_client()
        self.conf = mock.Mock()
        self.conf.metering_storage_engine = 'mongodb'
        self.conf.database_connection = 'mongodb://localhost/%s' % self.DBNAME
        self.conn = Connection(self.conf)
        self.conn.conn.drop_database(self.DBNAME)
        self.conn.conn[self.DBNAME]

        @self.app.before_request
        def attach_storage_connection():
            flask.request.storage_conn = self.conn
        return

    def tearDown(self):
        self.conn.conn.drop_database(self.DBNAME)

    def get(self, path):
        rv = self.test_app.get(path)
        try:
            data = json.loads(rv.data)
        except ValueError:
            print 'RAW DATA:', rv
            raise
        return data
