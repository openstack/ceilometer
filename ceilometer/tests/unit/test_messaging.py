# Copyright (C) 2014 eNovance SAS <licensing@enovance.com>
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

from oslo_config import fixture as fixture_config
import oslo_messaging.conffixture
from oslotest import base

from ceilometer import messaging


class MessagingTests(base.BaseTestCase):
    def setUp(self):
        super(MessagingTests, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.useFixture(oslo_messaging.conffixture.ConfFixture(self.CONF))

    def test_get_transport_invalid_url(self):
        self.assertRaises(oslo_messaging.InvalidTransportURL,
                          messaging.get_transport, "notvalid!")

    def test_get_transport_url_caching(self):
        t1 = messaging.get_transport('fake://')
        t2 = messaging.get_transport('fake://')
        self.assertEqual(t1, t2)

    def test_get_transport_default_url_caching(self):
        t1 = messaging.get_transport()
        t2 = messaging.get_transport()
        self.assertEqual(t1, t2)

    def test_get_transport_default_url_no_caching(self):
        t1 = messaging.get_transport(cache=False)
        t2 = messaging.get_transport(cache=False)
        self.assertNotEqual(t1, t2)

    def test_get_transport_url_no_caching(self):
        t1 = messaging.get_transport('fake://', cache=False)
        t2 = messaging.get_transport('fake://', cache=False)
        self.assertNotEqual(t1, t2)

    def test_get_transport_default_url_caching_mix(self):
        t1 = messaging.get_transport()
        t2 = messaging.get_transport(cache=False)
        self.assertNotEqual(t1, t2)

    def test_get_transport_url_caching_mix(self):
        t1 = messaging.get_transport('fake://')
        t2 = messaging.get_transport('fake://', cache=False)
        self.assertNotEqual(t1, t2)

    def test_get_transport_optional(self):
        self.CONF.set_override('rpc_backend', '')
        self.assertIsNone(messaging.get_transport(optional=True,
                                                  cache=False))
