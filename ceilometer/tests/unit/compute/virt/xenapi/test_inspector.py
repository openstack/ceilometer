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

from ceilometer.compute.virt.xenapi import inspector as xenapi_inspector
from ceilometer import service


class TestXenapiInspection(base.BaseTestCase):

    def setUp(self):
        super(TestXenapiInspection, self).setUp()
        conf = service.prepare_service([], [])
        api_session = mock.Mock()
        xenapi_inspector.get_api_session = mock.Mock(return_value=api_session)
        self.inspector = xenapi_inspector.XenapiInspector(conf)

    def test_inspect_instance(self):
        fake_instance = {'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
                         'id': 'fake_instance_id'}
        fake_total_mem = 134217728.0
        fake_free_mem = 65536.0

        session = self.inspector.session
        with mock.patch.object(session.VM, 'get_by_name_label') as mock_name, \
                mock.patch.object(session.VM, 'get_VCPUs_max') as mock_vcpu, \
                mock.patch.object(session.VM, 'query_data_source') \
                as mock_query:
            mock_name.return_value = ['vm_ref']
            mock_vcpu.return_value = '1'
            mock_query.side_effect = [0.4, fake_total_mem, fake_free_mem]
            stats = self.inspector.inspect_instance(fake_instance, None)
            self.assertEqual(40, stats.cpu_util)
            self.assertEqual(64, stats.memory_usage)

    def test_inspect_memory_usage_without_freeMem(self):
        fake_instance = {'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
                         'id': 'fake_instance_id'}
        fake_total_mem = 134217728.0
        fake_free_mem = 0

        session = self.inspector.session
        with mock.patch.object(session.VM, 'get_by_name_label') as mock_name, \
                mock.patch.object(session.VM, 'get_VCPUs_max') as mock_vcpu, \
                mock.patch.object(session.VM, 'query_data_source') \
                as mock_query:
            mock_name.return_value = ['vm_ref']
            mock_vcpu.return_value = '1'
            mock_query.side_effect = [0.4, fake_total_mem, fake_free_mem]
            stats = self.inspector.inspect_instance(fake_instance, None)
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
        bandwidth_returns = [{
            '10': {
                '0': {
                    'bw_in': 1024, 'bw_out': 2048
                }
            }
        }]
        session = self.inspector.session
        with mock.patch.object(session.VM, 'get_by_name_label') as mock_name, \
                mock.patch.object(session.VM, 'get_domid') as mock_domid, \
                mock.patch.object(session.VM, 'get_VIFs') as mock_vif, \
                mock.patch.object(session.VIF, 'get_record') as mock_record, \
                mock.patch.object(session, 'call_plugin_serialized') \
                as mock_plugin:
            mock_name.return_value = ['vm_ref']
            mock_domid.return_value = '10'
            mock_vif.return_value = ['vif_ref']
            mock_record.return_value = vif_rec
            mock_plugin.side_effect = bandwidth_returns
            interfaces = list(self.inspector.inspect_vnics(
                fake_instance, None))

            self.assertEqual(1, len(interfaces))
            vnic0 = interfaces[0]
            self.assertEqual('vif_uuid', vnic0.name)
            self.assertEqual('vif_mac', vnic0.mac)
            self.assertEqual(1024, vnic0.rx_bytes)
            self.assertEqual(2048, vnic0.tx_bytes)

    def test_inspect_vnic_rates(self):
        fake_instance = {'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
                         'id': 'fake_instance_id'}

        vif_rec = {
            'metrics': 'vif_metrics_ref',
            'uuid': 'vif_uuid',
            'MAC': 'vif_mac',
            'device': '0',
        }

        session = self.inspector.session
        with mock.patch.object(session.VM, 'get_by_name_label') as mock_name, \
                mock.patch.object(session.VM, 'get_VIFs') as mock_vif, \
                mock.patch.object(session.VIF, 'get_record') as mock_record, \
                mock.patch.object(session.VM, 'query_data_source') \
                as mock_query:
            mock_name.return_value = ['vm_ref']
            mock_vif.return_value = ['vif_ref']
            mock_record.return_value = vif_rec
            mock_query.side_effect = [1024.0, 2048.0]
            interfaces = list(self.inspector.inspect_vnic_rates(
                fake_instance, None))

            self.assertEqual(1, len(interfaces))
            vnic0 = interfaces[0]
            self.assertEqual('vif_uuid', vnic0.name)
            self.assertEqual('vif_mac', vnic0.mac)
            self.assertEqual(1024.0, vnic0.rx_bytes_rate)
            self.assertEqual(2048.0, vnic0.tx_bytes_rate)

    def test_inspect_disk_rates(self):
        fake_instance = {'OS-EXT-SRV-ATTR:instance_name': 'fake_instance_name',
                         'id': 'fake_instance_id'}

        vbd_rec = {
            'device': 'xvdd'
        }

        session = self.inspector.session
        with mock.patch.object(session.VM, 'get_by_name_label') as mock_name, \
                mock.patch.object(session.VM, 'get_VBDs') as mock_vbds, \
                mock.patch.object(session.VBD, 'get_record') as mock_records, \
                mock.patch.object(session.VM, 'query_data_source') \
                as mock_query:
            mock_name.return_value = ['vm_ref']
            mock_vbds.return_value = ['vbd_ref']
            mock_records.return_value = vbd_rec
            mock_query.side_effect = [1024.0, 2048.0]
            disks = list(self.inspector.inspect_disk_rates(
                fake_instance, None))

            self.assertEqual(1, len(disks))
            disk0 = disks[0]
            self.assertEqual('xvdd', disk0.device)
            self.assertEqual(1024.0, disk0.read_bytes_rate)
            self.assertEqual(2048.0, disk0.write_bytes_rate)
