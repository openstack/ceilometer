# Copyright 2014 Intel
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
"""Tests for xenapi inspector.
"""

import mock
from oslo_config import fixture as fixture_config
from oslotest import base

from ceilometer.compute.virt.xenapi import inspector as xenapi_inspector
from ceilometer import service
from ceilometer.tests.unit.compute.virt.xenapi import fake_XenAPI


class TestSwapXapiHost(base.BaseTestCase):

    def test_swapping(self):
        self.assertEqual(
            "http://otherserver:8765/somepath",
            xenapi_inspector.swap_xapi_host(
                "http://someserver:8765/somepath", 'otherserver'))

    def test_no_port(self):
        self.assertEqual(
            "http://otherserver/somepath",
            xenapi_inspector.swap_xapi_host(
                "http://someserver/somepath", 'otherserver'))

    def test_no_path(self):
        self.assertEqual(
            "http://otherserver",
            xenapi_inspector.swap_xapi_host(
                "http://someserver", 'otherserver'))

    def test_same_hostname_path(self):
        self.assertEqual(
            "http://other:80/some",
            xenapi_inspector.swap_xapi_host(
                "http://some:80/some", 'other'))


class TestXenapiInspection(base.BaseTestCase):

    def setUp(self):
        super(TestXenapiInspection, self).setUp()
        conf = service.prepare_service([], [])
        self.CONF = self.useFixture(fixture_config.Config(conf)).conf
        api_session = mock.Mock()
        xenapi_inspector.get_api_session = mock.Mock(return_value=api_session)
        self.inspector = xenapi_inspector.XenapiInspector(self.CONF)

    def test_inspect_instance(self):
        fake_instance = {'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
                         'id': 'fake_instance_id'}
        fake_total_mem = 134217728.0
        fake_free_mem = 65536.0

        def fake_xenapi_request(method, args):
            if method == 'VM.get_by_name_label':
                return ['vm_ref']
            elif method == 'VM.get_VCPUs_max':
                return '1'
            elif method == 'VM.query_data_source':
                if 'memory' in args:
                    return fake_total_mem
                elif 'memory_internal_free' in args:
                    return fake_free_mem
                elif 'cpu0' in args:
                    return 0.4
                else:
                    return None
            else:
                return None

        session = self.inspector.session
        with mock.patch.object(session, 'xenapi_request',
                               side_effect=fake_xenapi_request):
            stats = self.inspector.inspect_instance(fake_instance)
            self.assertEqual(40, stats.cpu_util)
            self.assertEqual(64, stats.memory_usage)

    def test_inspect_memory_usage_without_freeMem(self):
        fake_instance = {'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
                         'id': 'fake_instance_id'}

        def _fake_xenapi_request(method, args):
            if xenapi_inspector.api is None:
                # the XenAPI may not exist in the test environment.
                # In that case, we use the fake XenAPI for testing.
                xenapi_inspector.api = fake_XenAPI
            fake_total_mem = 134217728.0
            fake_details = ['INTERNAL_ERROR',
                            'Rrd.Invalid_data_source("memory_internal_free")']

            if method == 'VM.get_by_name_label':
                return ['vm_ref']
            elif method == 'VM.get_VCPUs_max':
                return '1'
            elif method == 'VM.query_data_source':
                if 'memory' in args:
                    return fake_total_mem
                elif 'memory_internal_free' in args:
                    raise xenapi_inspector.api.Failure(fake_details)
                elif 'cpu0' in args:
                    return 0.4
                else:
                    return None
            else:
                return None

        session = self.inspector.session
        with mock.patch.object(session, 'xenapi_request',
                               side_effect=_fake_xenapi_request):
            stats = self.inspector.inspect_instance(fake_instance)
            self.assertEqual(128, stats.memory_usage)

    def test_inspect_vnics(self):
        fake_instance = {
            'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
            'id': 'fake_instance_id'}
        vif_rec = {
            'uuid': 'vif_uuid',
            'MAC': 'vif_mac',
            'device': '0',
        }
        request_returns = [['vm_ref'], '10', ['vif_ref'], vif_rec]
        bandwidth_returns = [{
            '10': {
                '0': {
                    'bw_in': 1024, 'bw_out': 2048
                }
            }
        }]
        session = self.inspector.session
        with mock.patch.object(session, 'xenapi_request',
                               side_effect=request_returns):
            with mock.patch.object(self.inspector,
                                   '_call_plugin_serialized',
                                   side_effect=bandwidth_returns):

                interfaces = list(
                    self.inspector.inspect_vnics(fake_instance))

                self.assertEqual(1, len(interfaces))
                vnic0, info0 = interfaces[0]
                self.assertEqual('vif_uuid', vnic0.name)
                self.assertEqual('vif_mac', vnic0.mac)
                self.assertEqual(1024, info0.rx_bytes)
                self.assertEqual(2048, info0.tx_bytes)

    def test_inspect_vnic_rates(self):
        fake_instance = {'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
                         'id': 'fake_instance_id'}

        vif_rec = {
            'metrics': 'vif_metrics_ref',
            'uuid': 'vif_uuid',
            'MAC': 'vif_mac',
            'device': '0',
        }
        side_effects = [['vm_ref'], ['vif_ref'], vif_rec, 1024.0, 2048.0]

        session = self.inspector.session
        with mock.patch.object(session, 'xenapi_request',
                               side_effect=side_effects):
            interfaces = list(self.inspector.inspect_vnic_rates(fake_instance))

            self.assertEqual(1, len(interfaces))
            vnic0, info0 = interfaces[0]
            self.assertEqual('vif_uuid', vnic0.name)
            self.assertEqual('vif_mac', vnic0.mac)
            self.assertEqual(1024.0, info0.rx_bytes_rate)
            self.assertEqual(2048.0, info0.tx_bytes_rate)

    def test_inspect_disk_rates(self):
        fake_instance = {'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
                         'id': 'fake_instance_id'}

        vbd_rec = {
            'device': 'xvdd'
        }
        side_effects = [['vm_ref'], ['vbd_ref'], vbd_rec, 1024.0, 2048.0]

        session = self.inspector.session
        with mock.patch.object(session, 'xenapi_request',
                               side_effect=side_effects):
            disks = list(self.inspector.inspect_disk_rates(fake_instance))

            self.assertEqual(1, len(disks))
            disk0, info0 = disks[0]
            self.assertEqual('xvdd', disk0.device)
            self.assertEqual(1024.0, info0.read_bytes_rate)
            self.assertEqual(2048.0, info0.write_bytes_rate)
