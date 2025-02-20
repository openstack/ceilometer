#
# Copyright 2022 Red Hat, Inc
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
"""Tests for ceilometer/polling/prom_exporter.py"""

from oslotest import base

from unittest import mock
from unittest.mock import call

from ceilometer.polling import manager
from ceilometer.polling import prom_exporter
from ceilometer import service


COUNTER_SOURCE = 'testsource'


class TestPromExporter(base.BaseTestCase):
    test_disk_latency = [
        {
            'source': 'openstack',
            'counter_name': 'disk.device.read.latency',
            'counter_type': 'cumulative',
            'counter_unit': 'ns',
            'counter_volume': 132128682,
            'user_id': '6e7d71415cd5401cbe103829c9c5dec2',
            'user_name': None,
            'project_id': 'd965489b7f894cbda89cd2e25bfd85a0',
            'project_name': None,
            'resource_id': 'e536fff6-b20d-4aa5-ac2f-d15ac8b3af63-vda',
            'timestamp': '2024-06-20T09:32:36.521082',
            'resource_metadata': {
                'display_name': 'myserver',
                'name': 'instance-00000002',
                'instance_id': 'e536fff6-b20d-4aa5-ac2f-d15ac8b3af63',
                'instance_type': 'tiny',
                'host': 'e0d297f5df3b62ec73c8d42b',
                'instance_host': 'devstack',
                'flavor': {
                    'id': '4af9ac72-5787-4f86-8644-0faa87ce7c83',
                    'name': 'tiny',
                    'vcpus': 1,
                    'ram': 512,
                    'disk': 1,
                    'ephemeral': 0,
                    'swap': 0
                },
                'status': 'active',
                'state': 'running',
                'task_state': '',
                'image': {
                    'id': '71860ed5-f66d-43e0-9514-f1d188106284'
                },
                'image_ref': '71860ed5-f66d-43e0-9514-f1d188106284',
                'image_ref_url': None,
                'architecture': 'x86_64',
                'os_type': 'hvm',
                'vcpus': 1,
                'memory_mb': 512,
                'disk_gb': 1,
                'ephemeral_gb': 0,
                'root_gb': 1,
                'disk_name': 'vda',
                'user_metadata': {
                    'custom_label': 'custom value'
                }
            },
            'message_id': '078029c7-2ee8-11ef-a915-bd45e2085de3',
            'monotonic_time': 1819980.112406547,
            'message_signature': 'f8d9a411b0cd0cb0d34e83'
        },
        {
            'source': 'openstack',
            'counter_name': 'disk.device.read.latency',
            'counter_type': 'cumulative',
            'counter_unit': 'ns',
            'counter_volume': 232128754,
            'user_id': '6e7d71415cd5401cbe103829c9c5dec2',
            'user_name': None,
            'project_id': 'd965489b7f894cbda89cd2e25bfd85a0',
            'project_name': None,
            'resource_id': 'e536fff6-b20d-4aa5-ac2f-d15ac8b3af63-vda',
            'timestamp': '2024-06-20T09:32:46.521082',
            'resource_metadata': {
                'display_name': 'myserver',
                'name': 'instance-00000002',
                'instance_id': 'e536fff6-b20d-4aa5-ac2f-d15ac8b3af63',
                'instance_type': 'tiny',
                'host': 'e0d297f5df3b62ec73c8d42b',
                'instance_host': 'devstack',
                'flavor': {
                    'id': '4af9ac72-5787-4f86-8644-0faa87ce7c83',
                    'name': 'tiny',
                    'vcpus': 1,
                    'ram': 512,
                    'disk': 1,
                    'ephemeral': 0,
                    'swap': 0
                },
                'status': 'active',
                'state': 'running',
                'task_state': '',
                'image': {
                    'id': '71860ed5-f66d-43e0-9514-f1d188106284'
                },
                'image_ref': '71860ed5-f66d-43e0-9514-f1d188106284',
                'image_ref_url': None,
                'architecture': 'x86_64',
                'os_type': 'hvm',
                'vcpus': 1,
                'memory_mb': 512,
                'disk_gb': 1,
                'ephemeral_gb': 0,
                'root_gb': 1,
                'disk_name': 'vda',
                'user_metadata': {
                    'custom_label': 'custom value'
                }
            },
            'message_id': '078029c7-2ee8-11ef-a915-bd45e2085de4',
            'monotonic_time': 1819990.112406547,
            'message_signature': 'f8d9a411b0cd0cb0d34e84'
        }
    ]

    test_memory_usage = [
        {
            'source': 'openstack',
            'counter_name': 'memory.usage',
            'counter_type': 'gauge',
            'counter_unit': 'MB',
            'counter_volume': 37.98046875,
            'user_id': '6e7d71415cd5401cbe103829c9c5dec2',
            'user_name': None,
            'project_id': 'd965489b7f894cbda89cd2e25bfd85a0',
            'project_name': None,
            'resource_id': 'e536fff6-b20d-4aa5-ac2f-d15ac8b3af63',
            'timestamp': '2024-06-20T09:32:36.515823',
            'resource_metadata': {
                'display_name': 'myserver',
                'name': 'instance-00000002',
                'instance_id': 'e536fff6-b20d-4aa5-ac2f-d15ac8b3af63',
                'instance_type': 'tiny',
                'host': 'e0d297f5df3b62ec73c8d42b',
                'instance_host': 'devstack',
                'flavor': {
                    'id': '4af9ac72-5787-4f86-8644-0faa87ce7c83',
                    'name': 'tiny',
                    'vcpus': 1,
                    'ram': 512,
                    'disk': 1,
                    'ephemeral': 0,
                    'swap': 0
                },
                'status': 'active',
                'state': 'running',
                'task_state': '',
                'image': {
                    'id': '71860ed5-f66d-43e0-9514-f1d188106284'
                },
                'image_ref': '71860ed5-f66d-43e0-9514-f1d188106284',
                'image_ref_url': None,
                'architecture': 'x86_64',
                'os_type': 'hvm',
                'vcpus': 1,
                'memory_mb': 512,
                'disk_gb': 1,
                'ephemeral_gb': 0,
                'root_gb': 1
            },
            'message_id': '078029bf-2ee8-11ef-a915-bd45e2085de3',
            'monotonic_time': 1819980.131767362,
            'message_signature': 'f8d9a411b0cd0cb0d34e83'
        }
    ]

    test_image_size = [
        {
            'source': 'openstack',
            'counter_name': 'image.size',
            'counter_type': 'gauge',
            'counter_unit': 'B',
            'counter_volume': 16344576,
            'user_id': None,
            'user_name': None,
            'project_id': 'd965489b7f894cbda89cd2e25bfd85a0',
            'project_name': None,
            'resource_id': 'f9276c96-8a12-432b-96a1-559d70715f97',
            'timestamp': '2024-06-20T09:40:17.118871',
            'resource_metadata': {
                'status': 'active',
                'visibility': 'public',
                'name': 'cirros2',
                'container_format': 'bare',
                'created_at': '2024-05-30T11:38:52Z',
                'disk_format': 'qcow2',
                'updated_at': '2024-05-30T11:38:52Z',
                'min_disk': 0,
                'protected': False,
                'checksum': '7734eb3945297adc90ddc6cebe8bb082',
                'min_ram': 0,
                'tags': [],
                'virtual_size': 117440512,
                'user_metadata': {
                    'server_group': 'server_group123'
                }
            },
            'message_id': '19f8f78a-2ee9-11ef-a95f-bd45e2085de3',
            'monotonic_time': None,
            'message_signature': 'f8d9a411b0cd0cb0d34e83'
        }
    ]

    @mock.patch('ceilometer.polling.prom_exporter.export')
    def test_prom_disabled(self, export):
        CONF = service.prepare_service([], [])
        manager.AgentManager(0, CONF)

        export.assert_not_called()

    @mock.patch('ceilometer.polling.prom_exporter.export')
    def test_export_called(self, export):
        CONF = service.prepare_service([], [])
        CONF.polling.enable_prometheus_exporter = True
        CONF.polling.prometheus_listen_addresses = [
            '127.0.0.1:9101',
            '127.0.0.1:9102',
            '[::1]:9103',
            'localhost:9104',
        ]
        manager.AgentManager(0, CONF)

        export.assert_has_calls([
            call('127.0.0.1', 9101),
            call('127.0.0.1', 9102),
            call('::1', 9103),
            call('localhost', 9104),
        ])

    def test_collect_metrics(self):
        prom_exporter.collect_metrics(self.test_image_size)
        sample_dict_1 = {'counter': 'image.size',
                         'image': 'f9276c96-8a12-432b-96a1-559d70715f97',
                         'project': 'd965489b7f894cbda89cd2e25bfd85a0',
                         'publisher': 'ceilometer',
                         'resource': 'f9276c96-8a12-432b-96a1-559d70715f97',
                         'resource_name': 'cirros2',
                         'type': 'size',
                         'unit': 'B',
                         'server_group': 'server_group123'}
        self.assertEqual(16344576,
                         prom_exporter.CEILOMETER_REGISTRY.
                         get_sample_value('ceilometer_image_size',
                                          sample_dict_1))

        prom_exporter.collect_metrics(self.test_memory_usage)
        sample_dict_2 = {'counter': 'memory.usage',
                         'memory': 'e536fff6-b20d-4aa5-ac2f-d15ac8b3af63',
                         'project': 'd965489b7f894cbda89cd2e25bfd85a0',
                         'publisher': 'ceilometer',
                         'resource': 'e536fff6-b20d-4aa5-ac2f-d15ac8b3af63',
                         'resource_name': 'myserver:instance-00000002',
                         'type': 'usage',
                         'unit': 'MB',
                         'user': '6e7d71415cd5401cbe103829c9c5dec2',
                         'vm_instance': 'e0d297f5df3b62ec73c8d42b',
                         'server_group': 'none'}
        self.assertEqual(37.98046875,
                         prom_exporter.CEILOMETER_REGISTRY.
                         get_sample_value('ceilometer_memory_usage',
                                          sample_dict_2))

        prom_exporter.collect_metrics(self.test_disk_latency)
        sample_dict_3 = {'counter': 'disk.device.read.latency',
                         'disk': 'read',
                         'project': 'd965489b7f894cbda89cd2e25bfd85a0',
                         'publisher': 'ceilometer',
                         'resource':
                         'e536fff6-b20d-4aa5-ac2f-d15ac8b3af63-vda',
                         'resource_name': 'myserver:instance-00000002',
                         'type': 'device',
                         'unit': 'ns',
                         'user': '6e7d71415cd5401cbe103829c9c5dec2',
                         'vm_instance': 'e0d297f5df3b62ec73c8d42b',
                         'server_group': 'none'}
        # The value has to be of the second sample, as this is now a Gauge
        self.assertEqual(232128754,
                         prom_exporter.CEILOMETER_REGISTRY.
                         get_sample_value(
                             'ceilometer_disk_device_read_latency',
                             sample_dict_3))

    def test_gen_labels(self):
        slabels1 = dict(keys=[], values=[])
        slabels1['keys'] = ['disk', 'publisher', 'type', 'counter',
                            'project', 'user', 'unit', 'resource',
                            'vm_instance', 'resource_name',
                            'server_group']
        slabels1['values'] = ['read', 'ceilometer', 'device',
                              'disk.device.read.latency',
                              'd965489b7f894cbda89cd2e25bfd85a0',
                              '6e7d71415cd5401cbe103829c9c5dec2',
                              'ns',
                              'e536fff6-b20d-4aa5-ac2f-d15ac8b3af63-vda',
                              'e0d297f5df3b62ec73c8d42b',
                              'myserver:instance-00000002', 'none']
        label1 = prom_exporter._gen_labels(self.test_disk_latency[0])
        self.assertDictEqual(label1, slabels1)

        slabels2 = dict(keys=[], values=[])
        slabels2['keys'] = ['memory', 'publisher', 'type', 'counter',
                            'project', 'user', 'unit', 'resource',
                            'vm_instance', 'resource_name',
                            'server_group']
        slabels2['values'] = ['e536fff6-b20d-4aa5-ac2f-d15ac8b3af63',
                              'ceilometer', 'usage', 'memory.usage',
                              'd965489b7f894cbda89cd2e25bfd85a0',
                              '6e7d71415cd5401cbe103829c9c5dec2', 'MB',
                              'e536fff6-b20d-4aa5-ac2f-d15ac8b3af63',
                              'e0d297f5df3b62ec73c8d42b',
                              'myserver:instance-00000002', 'none']
        label2 = prom_exporter._gen_labels(self.test_memory_usage[0])
        self.assertDictEqual(label2, slabels2)

        slabels3 = dict(keys=[], values=[])
        slabels3['keys'] = ['image', 'publisher', 'type', 'counter',
                            'project', 'unit', 'resource',
                            'resource_name', 'server_group']
        slabels3['values'] = ['f9276c96-8a12-432b-96a1-559d70715f97',
                              'ceilometer', 'size', 'image.size',
                              'd965489b7f894cbda89cd2e25bfd85a0', 'B',
                              'f9276c96-8a12-432b-96a1-559d70715f97',
                              'cirros2', 'server_group123']
        label3 = prom_exporter._gen_labels(self.test_image_size[0])
        self.assertDictEqual(label3, slabels3)
