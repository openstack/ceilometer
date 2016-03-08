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
from oslotest import base

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.compute.virt.xenapi import inspector as xenapi_inspector


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
        api_session = mock.Mock()
        xenapi_inspector.get_api_session = mock.Mock(return_value=api_session)
        self.inspector = xenapi_inspector.XenapiInspector()

        super(TestXenapiInspection, self).setUp()

    def test_inspect_cpu_util(self):
        fake_instance = {'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
                         'id': 'fake_instance_id'}
        fake_stat = virt_inspector.CPUUtilStats(util=40)

        def fake_xenapi_request(method, args):
            metrics_rec = {
                'memory_actual': '536870912',
                'VCPUs_number': '1',
                'VCPUs_utilisation': {'0': 0.4, }
            }

            if method == 'VM.get_by_name_label':
                return ['vm_ref']
            elif method == 'VM.get_metrics':
                return 'metrics_ref'
            elif method == 'VM_metrics.get_record':
                return metrics_rec
            else:
                return None

        session = self.inspector.session
        with mock.patch.object(session, 'xenapi_request',
                               side_effect=fake_xenapi_request):
            cpu_util_stat = self.inspector.inspect_cpu_util(fake_instance)
            self.assertEqual(fake_stat, cpu_util_stat)

    def test_inspect_memory_usage(self):
        fake_instance = {'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
                         'id': 'fake_instance_id'}
        fake_stat = virt_inspector.MemoryUsageStats(usage=128)

        def fake_xenapi_request(method, args):
            metrics_rec = {
                'memory_actual': '134217728',
            }

            if method == 'VM.get_by_name_label':
                return ['vm_ref']
            elif method == 'VM.get_metrics':
                return 'metrics_ref'
            elif method == 'VM_metrics.get_record':
                return metrics_rec
            else:
                return None

        session = self.inspector.session
        with mock.patch.object(session, 'xenapi_request',
                               side_effect=fake_xenapi_request):
            memory_stat = self.inspector.inspect_memory_usage(fake_instance)
            self.assertEqual(fake_stat, memory_stat)

    def test_inspect_vnic_rates(self):
        fake_instance = {'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
                         'id': 'fake_instance_id'}

        def fake_xenapi_request(method, args):
            vif_rec = {
                'metrics': 'vif_metrics_ref',
                'uuid': 'vif_uuid',
                'MAC': 'vif_mac',
            }

            vif_metrics_rec = {
                'io_read_kbs': '1',
                'io_write_kbs': '2',
            }
            if method == 'VM.get_by_name_label':
                return ['vm_ref']
            elif method == 'VM.get_VIFs':
                return ['vif_ref']
            elif method == 'VIF.get_record':
                return vif_rec
            elif method == 'VIF.get_metrics':
                return 'vif_metrics_ref'
            elif method == 'VIF_metrics.get_record':
                return vif_metrics_rec
            else:
                return None

        session = self.inspector.session
        with mock.patch.object(session, 'xenapi_request',
                               side_effect=fake_xenapi_request):
            interfaces = list(self.inspector.inspect_vnic_rates(fake_instance))

            self.assertEqual(1, len(interfaces))
            vnic0, info0 = interfaces[0]
            self.assertEqual('vif_uuid', vnic0.name)
            self.assertEqual('vif_mac', vnic0.mac)
            self.assertEqual(1024, info0.rx_bytes_rate)
            self.assertEqual(2048, info0.tx_bytes_rate)

    def test_inspect_disk_rates(self):
        fake_instance = {'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
                         'id': 'fake_instance_id'}

        def fake_xenapi_request(method, args):
            vbd_rec = {
                'device': 'xvdd'
            }

            vbd_metrics_rec = {
                'io_read_kbs': '1',
                'io_write_kbs': '2'
            }
            if method == 'VM.get_by_name_label':
                return ['vm_ref']
            elif method == 'VM.get_VBDs':
                return ['vbd_ref']
            elif method == 'VBD.get_record':
                return vbd_rec
            elif method == 'VBD.get_metrics':
                return 'vbd_metrics_ref'
            elif method == 'VBD_metrics.get_record':
                return vbd_metrics_rec
            else:
                return None

        session = self.inspector.session
        with mock.patch.object(session, 'xenapi_request',
                               side_effect=fake_xenapi_request):
            disks = list(self.inspector.inspect_disk_rates(fake_instance))

            self.assertEqual(1, len(disks))
            disk0, info0 = disks[0]
            self.assertEqual('xvdd', disk0.device)
            self.assertEqual(1024, info0.read_bytes_rate)
            self.assertEqual(2048, info0.write_bytes_rate)
