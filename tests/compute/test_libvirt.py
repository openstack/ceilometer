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
    import libvirt as ignored_libvirt
except ImportError:
    libvirt_missing = True
else:
    libvirt_missing = False

from nova import context
from nova import flags
from nova import test
from nova import db

from ceilometer.compute import libvirt
from ceilometer.compute import manager


class TestDiskIOPollster(test.TestCase):

    def setUp(self):
        self.context = context.RequestContext('admin', 'admin', is_admin=True)
        self.manager = manager.AgentManager()
        self.pollster = libvirt.DiskIOPollster()
        super(TestDiskIOPollster, self).setUp()
        self.instance = db.instance_create(self.context, {})
        flags.FLAGS.compute_driver = 'libvirt.LibvirtDriver'

    @test.skip_if(libvirt_missing, 'Test requires libvirt')
    def test_fetch_diskio(self):
        counters = list(self.pollster.get_counters(self.manager,
                                                   self.instance))
        #assert counters
        # FIXME(dhellmann): The CI environment doesn't produce
        # a response when the fake driver asks for the disks, so
        # we do not get any counters in response.

    @test.skip_if(libvirt_missing, 'Test requires libvirt')
    def test_fetch_diskio_not_libvirt(self):
        flags.FLAGS.compute_driver = 'fake.FakeDriver'
        counters = list(self.pollster.get_counters(self.manager,
                                                   self.instance))
        assert not counters

    @test.skip_if(libvirt_missing, 'Test requires libvirt')
    def test_fetch_diskio_with_libvirt_non_existent_instance(self):
        print 'ID:', self.instance.id
        inst = db.instance_get(self.context, self.instance.id)
        inst.id = 999  # change the id so the driver cannot find the instance
        counters = list(self.pollster.get_counters(self.manager, inst))
        assert not counters
