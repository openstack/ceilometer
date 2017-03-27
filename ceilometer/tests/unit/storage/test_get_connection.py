#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
"""Tests for ceilometer/storage/
"""
import mock
from oslotest import base

from ceilometer import service
from ceilometer import storage
from ceilometer.storage import impl_log
from ceilometer.storage import impl_sqlalchemy

import six


class EngineTest(base.BaseTestCase):
    def setUp(self):
        super(EngineTest, self).setUp()
        self.CONF = service.prepare_service([], [])

    def test_get_connection(self):
        engine = storage.get_connection(self.CONF,
                                        'log://localhost')
        self.assertIsInstance(engine, impl_log.Connection)

    def test_get_connection_no_such_engine(self):
        try:
            storage.get_connection(self.CONF,
                                   'no-such-engine://localhost')
        except RuntimeError as err:
            self.assertIn('no-such-engine', six.text_type(err))


class ConnectionRetryTest(base.BaseTestCase):
    def setUp(self):
        super(ConnectionRetryTest, self).setUp()
        self.CONF = service.prepare_service([], [])

    def test_retries(self):
        with mock.patch.object(storage, 'get_connection') as retries:
            try:
                self.CONF.set_override("connection", "no-such-engine://",
                                       group="database")
                self.CONF.set_override("retry_interval", 0.00001,
                                       group="database")
                storage.get_connection_from_config(self.CONF)
            except RuntimeError:
                self.assertEqual(10, retries.call_count)


class ConnectionConfigTest(base.BaseTestCase):
    def setUp(self):
        super(ConnectionConfigTest, self).setUp()
        self.CONF = service.prepare_service([], [])

    def test_only_default_url(self):
        self.CONF.set_override("connection", "log://", group="database")
        conn = storage.get_connection_from_config(self.CONF)
        self.assertIsInstance(conn, impl_log.Connection)

    def test_two_urls(self):
        self.CONF.set_override("connection", "log://", group="database")
        conn = storage.get_connection_from_config(self.CONF)
        self.assertIsInstance(conn, impl_log.Connection)

    def test_sqlalchemy_driver(self):
        self.CONF.set_override("connection", "sqlite+pysqlite://",
                               group="database")
        conn = storage.get_connection_from_config(self.CONF)
        self.assertIsInstance(conn, impl_sqlalchemy.Connection)
