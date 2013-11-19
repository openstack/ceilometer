# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
# Copyright © 2012 Red Hat, Inc
#
# Author: Julien Danjou <julien@danjou.info>
# Author: Eoghan Glynn <eglynn@redhat.com>
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

import mock

from ceilometer.compute import manager
from ceilometer.compute.pollsters import net
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.tests.compute.pollsters import base


class TestNetPollster(base.TestPollsterBase):

    def setUp(self):
        super(TestNetPollster, self).setUp()
        self.vnic0 = virt_inspector.Interface(
            name='vnet0',
            fref='fa163e71ec6e',
            mac='fa:16:3e:71:ec:6d',
            parameters=dict(ip='10.0.0.2',
                            projmask='255.255.255.0',
                            projnet='proj1',
                            dhcp_server='10.0.0.1'))
        stats0 = virt_inspector.InterfaceStats(rx_bytes=1L, rx_packets=2L,
                                               tx_bytes=3L, tx_packets=4L)
        self.vnic1 = virt_inspector.Interface(
            name='vnet1',
            fref='fa163e71ec6f',
            mac='fa:16:3e:71:ec:6e',
            parameters=dict(ip='192.168.0.3',
                            projmask='255.255.255.0',
                            projnet='proj2',
                            dhcp_server='10.0.0.2'))
        stats1 = virt_inspector.InterfaceStats(rx_bytes=5L, rx_packets=6L,
                                               tx_bytes=7L, tx_packets=8L)
        self.vnic2 = virt_inspector.Interface(
            name='vnet2',
            fref=None,
            mac='fa:18:4e:72:fc:7e',
            parameters=dict(ip='192.168.0.4',
                            projmask='255.255.255.0',
                            projnet='proj3',
                            dhcp_server='10.0.0.3'))
        stats2 = virt_inspector.InterfaceStats(rx_bytes=9L, rx_packets=10L,
                                               tx_bytes=11L, tx_packets=12L)

        vnics = [
            (self.vnic0, stats0),
            (self.vnic1, stats1),
            (self.vnic2, stats2),
        ]
        self.inspector.inspect_vnics = mock.Mock(return_value=vnics)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def _check_get_samples(self, factory, expected):
        mgr = manager.AgentManager()
        pollster = factory()
        samples = list(pollster.get_samples(mgr, {}, self.instance))
        self.assertEqual(len(samples), 3)  # one for each nic
        self.assertEqual(set([s.name for s in samples]),
                         set([samples[0].name]))

        def _verify_vnic_metering(ip, expected_volume, expected_rid):
            match = [s for s in samples
                     if s.resource_metadata['parameters']['ip'] == ip
                     ]
            self.assertEqual(len(match), 1, 'missing ip %s' % ip)
            self.assertEqual(match[0].volume, expected_volume)
            self.assertEqual(match[0].type, 'cumulative')
            self.assertEqual(match[0].resource_id, expected_rid)

        for ip, volume, rid in expected:
            _verify_vnic_metering(ip, volume, rid)

    def test_incoming_bytes(self):
        instance_name_id = "%s-%s" % (self.instance.name, self.instance.id)
        self._check_get_samples(
            net.IncomingBytesPollster,
            [('10.0.0.2', 1L, self.vnic0.fref),
             ('192.168.0.3', 5L, self.vnic1.fref),
             ('192.168.0.4', 9L,
              "%s-%s" % (instance_name_id, self.vnic2.name)),
             ],
        )

    def test_outgoing_bytes(self):
        instance_name_id = "%s-%s" % (self.instance.name, self.instance.id)
        self._check_get_samples(
            net.OutgoingBytesPollster,
            [('10.0.0.2', 3L, self.vnic0.fref),
             ('192.168.0.3', 7L, self.vnic1.fref),
             ('192.168.0.4', 11L,
              "%s-%s" % (instance_name_id, self.vnic2.name)),
             ],
        )

    def test_incoming_packets(self):
        instance_name_id = "%s-%s" % (self.instance.name, self.instance.id)
        self._check_get_samples(
            net.IncomingPacketsPollster,
            [('10.0.0.2', 2L, self.vnic0.fref),
             ('192.168.0.3', 6L, self.vnic1.fref),
             ('192.168.0.4', 10L,
              "%s-%s" % (instance_name_id, self.vnic2.name)),
             ],
        )

    def test_outgoing_packets(self):
        instance_name_id = "%s-%s" % (self.instance.name, self.instance.id)
        self._check_get_samples(
            net.OutgoingPacketsPollster,
            [('10.0.0.2', 4L, self.vnic0.fref),
             ('192.168.0.3', 8L, self.vnic1.fref),
             ('192.168.0.4', 12L,
              "%s-%s" % (instance_name_id, self.vnic2.name)),
             ],
        )


class TestNetPollsterCache(base.TestPollsterBase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def _check_get_samples_cache(self, factory):
        vnic0 = virt_inspector.Interface(
            name='vnet0',
            fref='fa163e71ec6e',
            mac='fa:16:3e:71:ec:6d',
            parameters=dict(ip='10.0.0.2',
                            projmask='255.255.255.0',
                            projnet='proj1',
                            dhcp_server='10.0.0.1'))
        stats0 = virt_inspector.InterfaceStats(rx_bytes=1L, rx_packets=2L,
                                               tx_bytes=3L, tx_packets=4L)
        vnics = [(vnic0, stats0)]

        mgr = manager.AgentManager()
        pollster = factory()
        cache = {
            pollster.CACHE_KEY_VNIC: {
                self.instance.name: vnics,
            },
        }
        samples = list(pollster.get_samples(mgr, cache, self.instance))
        self.assertEqual(len(samples), 1)

    def test_incoming_bytes(self):
        self._check_get_samples_cache(net.IncomingBytesPollster)

    def test_outgoing_bytes(self):
        self._check_get_samples_cache(net.OutgoingBytesPollster)

    def test_incoming_packets(self):
        self._check_get_samples_cache(net.IncomingPacketsPollster)

    def test_outgoing_packets(self):
        self._check_get_samples_cache(net.OutgoingPacketsPollster)
