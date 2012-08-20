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

import unittest

try:
    import libvirt as ignored_libvirt
except ImportError:
    libvirt_missing = True
else:
    libvirt_missing = False

import mock

from nova import flags

from ceilometer.compute import libvirt
from ceilometer.compute import manager
from ceilometer.tests import skip


class TestDiskIOPollster(unittest.TestCase):

    def setUp(self):
        self.manager = manager.AgentManager()
        self.pollster = libvirt.DiskIOPollster()
        super(TestDiskIOPollster, self).setUp()
        self.instance = mock.MagicMock()
        self.instance.name = 'instance-00000001'
        self.instance.id = 1
        flags.FLAGS.compute_driver = 'libvirt.LibvirtDriver'
        flags.FLAGS.connection_type = 'libvirt'

    @skip.skip_if(libvirt_missing, 'Test requires libvirt')
    def test_fetch_diskio(self):
        list(self.pollster.get_counters(self.manager, self.instance))
        #assert counters
        # FIXME(dhellmann): The CI environment doesn't produce
        # a response when the fake driver asks for the disks, so
        # we do not get any counters in response.

    @skip.skip_if(libvirt_missing, 'Test requires libvirt')
    def test_fetch_diskio_not_libvirt(self):
        flags.FLAGS.compute_driver = 'fake.FakeDriver'
        flags.FLAGS.connection_type = 'fake'
        counters = list(self.pollster.get_counters(self.manager,
                                                   self.instance))
        assert not counters

    @skip.skip_if(libvirt_missing, 'Test requires libvirt')
    def test_fetch_diskio_with_libvirt_non_existent_instance(self):
        instance = mock.MagicMock()
        instance.name = 'instance-00000999'
        instance.id = 999
        counters = list(self.pollster.get_counters(self.manager, instance))
        assert not counters
