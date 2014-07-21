#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
"""Tests for ceilometer/storage/
"""

from ceilometer.alarm.storage import impl_log as impl_log_alarm
from ceilometer.alarm.storage import impl_sqlalchemy as impl_sqlalchemy_alarm
from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common import test
from ceilometer import storage
from ceilometer.storage import impl_log

import six


class EngineTest(test.BaseTestCase):

    def test_get_connection(self):
        engine = storage.get_connection('log://localhost',
                                        'ceilometer.metering.storage')._conn
        self.assertIsInstance(engine, impl_log.Connection)

    def test_get_connection_no_such_engine(self):
        try:
            storage.get_connection('no-such-engine://localhost',
                                   'ceilometer.metering.storage')
        except RuntimeError as err:
            self.assertIn('no-such-engine', six.text_type(err))


class ConnectionConfigTest(test.BaseTestCase):
    def setUp(self):
        super(ConnectionConfigTest, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf

    def test_only_default_url(self):
        self.CONF.set_override("connection", "log://", group="database")
        conn = storage.get_connection_from_config(self.CONF)._conn
        self.assertIsInstance(conn, impl_log.Connection)
        conn = storage.get_connection_from_config(self.CONF, 'metering')._conn
        self.assertIsInstance(conn, impl_log.Connection)
        conn = storage.get_connection_from_config(self.CONF, 'alarm')._conn
        self.assertIsInstance(conn, impl_log_alarm.Connection)

    def test_two_urls(self):
        self.CONF.set_override("connection", "log://", group="database")
        self.CONF.set_override("alarm_connection", "sqlite://",
                               group="database")
        conn = storage.get_connection_from_config(self.CONF)._conn
        self.assertIsInstance(conn, impl_log.Connection)
        conn = storage.get_connection_from_config(self.CONF, 'metering')._conn
        self.assertIsInstance(conn, impl_log.Connection)
        conn = storage.get_connection_from_config(self.CONF, 'alarm')._conn
        self.assertIsInstance(conn, impl_sqlalchemy_alarm.Connection)
