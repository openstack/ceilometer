#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
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

from nova import context
from nova import test
from nova import db

from ceilometer.compute import network
from ceilometer.agent import manager


class TestFloatingIPPollster(test.TestCase):

    def setUp(self):
        self.context = context.RequestContext('admin', 'admin', is_admin=True)
        self.manager = manager.AgentManager()
        self.pollster = network.FloatingIPPollster()
        super(TestFloatingIPPollster, self).setUp()

    def test_get_counters(self):
        self.assertEqual(list(self.pollster.get_counters(self.manager,
                                                         self.context)),
                         [])

    def test_get_counters_not_empty(self):
        db.floating_ip_create(self.context,
                              {'address': '1.1.1.1',
                               'host': self.manager.host,
                               })
        db.floating_ip_create(self.context,
                              {'address': '1.1.1.2',
                               'host': self.manager.host + "randomstring",
                               })
        db.floating_ip_create(self.context,
                              {'address': '1.1.1.3',
                               'host': self.manager.host + "randomstring",
                               })
        counters = list(self.pollster.get_counters(self.manager, self.context))
        self.assertEqual(len(counters), 1)
        self.assertEqual(counters[0].resource_metadata['address'], '1.1.1.1')
