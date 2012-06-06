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
"""Tests for manager.
"""

try:
    import libvirt
except ImportError:
    libvirt_missing = True
else:
    libvirt_missing = False

from nova import context
from nova import flags
from nova import test
from nova import db

from ceilometer.compute import libvirt
from ceilometer.agent import manager


class TestDiskIOPollster(test.TestCase):

    def setUp(self):
        self.context = context.RequestContext('admin', 'admin', is_admin=True)
        self.manager = manager.AgentManager()
        self.pollster = libvirt.DiskIOPollster()
        super(TestDiskIOPollster, self).setUp()

    @test.skip_if(libvirt_missing, 'Test requires libvirt')
    def test_fetch_diskio(self):
        list(self.pollster.get_counters(self.manager, self.context))

    @test.skip_if(libvirt_missing, 'Test requires libvirt')
    def test_fetch_diskio_with_libvirt_non_existent_instance(self):
        flags.FLAGS.connection_type = 'libvirt'

        instance = db.instance_create(self.context, {})

        self.mox.StubOutWithMock(self.manager.db, 'instance_get_all_by_host')
        self.manager.db.instance_get_all_by_host(self.context,
                                                 self.manager.host,
                                                 ).AndReturn([instance])

        self.mox.ReplayAll()

        list(self.pollster.get_counters(self.manager, self.context))
