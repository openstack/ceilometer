# Copyright 2015 Huawei Technologies Co., Ltd.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import oslo_messaging

from ceilometer.api import hooks
from ceilometer import service
from ceilometer.tests import base


class TestTestNotifierHook(base.BaseTestCase):

    def setUp(self):
        super(TestTestNotifierHook, self).setUp()
        self.CONF = service.prepare_service([], [])

    def test_init_notifier_with_drivers(self):
        hook = hooks.NotifierHook(self.CONF)
        notifier = hook.notifier
        self.assertIsInstance(notifier, oslo_messaging.Notifier)
        self.assertEqual(['messagingv2'], notifier._driver_names)
