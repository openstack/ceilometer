#
# Copyright 2013 Intel Corp
#
# Authors: Lianhao Lu <lianhao.lu@intel.com>
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

import fixtures
import mock

from ceilometer.central import manager
from ceilometer.hardware.inspector import base as inspector_base
from ceilometer.tests import base as test_base


class FakeInspector(inspector_base.Inspector):
    net_metadata = dict(name='test.teest',
                        mac='001122334455',
                        ip='10.0.0.2',
                        speed=1000)
    disk_metadata = dict(device='/dev/sda1', path='/')
    DATA = {
        'cpu.load.1min': (0.99, {}, {}),
        'cpu.load.5min': (0.77, {}, {}),
        'cpu.load.15min': (0.55, {}, {}),
        'memory.total': (1000, {}, {}),
        'memory.used': (90, {}, {}),
        'network.incoming.bytes': (90, net_metadata, {}),
        'network.outgoing.bytes': (80, net_metadata, {}),
        'network.outgoing.errors': (1, net_metadata, {}),
        'disk.size.total': (1000, disk_metadata, {}),
        'disk.size.used': (90, disk_metadata, {}),
    }

    def inspect_generic(self, host, identifier, cache):
        yield self.DATA[identifier]


class TestPollsterBase(test_base.BaseTestCase):
    def faux_get_inspector(url, namespace=None):
        return FakeInspector()

    def setUp(self):
        super(TestPollsterBase, self).setUp()
        self.hosts = ["test://test", "test://test2"]
        self.useFixture(fixtures.MonkeyPatch(
            'ceilometer.hardware.inspector.get_inspector',
            self.faux_get_inspector))

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def _check_get_samples(self, factory, name,
                           expected_value, expected_type, expected_unit=None):
        mgr = manager.AgentManager()
        pollster = factory()
        cache = {}
        samples = list(pollster.get_samples(mgr, cache, self.hosts))
        self.assertTrue(samples)
        self.assertIn(pollster.CACHE_KEY, cache)
        for host in self.hosts:
            self.assertIn(host, cache[pollster.CACHE_KEY])

        self.assertEqual(set([name]),
                         set([s.name for s in samples]))
        match = [s for s in samples if s.name == name]
        self.assertEqual(expected_value, match[0].volume)
        self.assertEqual(expected_type, match[0].type)
        if expected_unit:
            self.assertEqual(expected_unit, match[0].unit)
