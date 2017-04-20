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

import oslo_messaging.conffixture
from oslotest import base

from ceilometer import messaging
from ceilometer import service


class MessagingTests(base.BaseTestCase):
    def setUp(self):
        super(MessagingTests, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.useFixture(oslo_messaging.conffixture.ConfFixture(self.CONF))

    def test_get_transport_invalid_url(self):
        self.assertRaises(oslo_messaging.InvalidTransportURL,
                          messaging.get_transport, self.CONF, "notvalid!")

    def test_get_transport_url_caching(self):
        t1 = messaging.get_transport(self.CONF, 'fake://')
        t2 = messaging.get_transport(self.CONF, 'fake://')
        self.assertEqual(t1, t2)

    def test_get_transport_default_url_caching(self):
        t1 = messaging.get_transport(self.CONF)
        t2 = messaging.get_transport(self.CONF)
        self.assertEqual(t1, t2)

    def test_get_transport_default_url_no_caching(self):
        t1 = messaging.get_transport(self.CONF, cache=False)
        t2 = messaging.get_transport(self.CONF, cache=False)
        self.assertNotEqual(t1, t2)

    def test_get_transport_url_no_caching(self):
        t1 = messaging.get_transport(self.CONF, 'fake://', cache=False)
        t2 = messaging.get_transport(self.CONF, 'fake://', cache=False)
        self.assertNotEqual(t1, t2)

    def test_get_transport_default_url_caching_mix(self):
        t1 = messaging.get_transport(self.CONF)
        t2 = messaging.get_transport(self.CONF, cache=False)
        self.assertNotEqual(t1, t2)

    def test_get_transport_url_caching_mix(self):
        t1 = messaging.get_transport(self.CONF, 'fake://')
        t2 = messaging.get_transport(self.CONF, 'fake://', cache=False)
        self.assertNotEqual(t1, t2)

    def test_get_transport_optional(self):
        self.CONF.set_override('transport_url', 'non-url')
        self.assertIsNone(messaging.get_transport(self.CONF,
                                                  optional=True,
                                                  cache=False))
