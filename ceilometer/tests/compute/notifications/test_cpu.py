# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Intel
#
# Author: Shuangtai Tian <Shuangtai.tian@intel.com>
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
"""Tests for converters for producing compute counter messages from
notification events.
"""

import copy

from ceilometer.compute.notifications import cpu
from ceilometer.openstack.common import test


METRICS_UPDATE = {
    u'_context_request_id': u'req-a8bfa89b-d28b-4b95-9e4b-7d7875275650',
    u'_context_quota_class': None,
    u'event_type': u'compute.metrics.update',
    u'_context_service_catalog': [],
    u'_context_auth_token': None,
    u'_context_user_id': None,
    u'payload': {
        u'metrics': [
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.frequency', 'value': 1600,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.user.time', 'value': 17421440000000L,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.kernel.time', 'value': 7852600000000L,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.idle.time', 'value': 1307374400000000L,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.iowait.time', 'value': 11697470000000L,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.user.percent', 'value': 0.012959045637294348,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.kernel.percent', 'value': 0.005841204961898534,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.idle.percent', 'value': 0.9724985141658965,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.iowait.percent', 'value': 0.008701235234910634,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.percent', 'value': 0.027501485834103515,
             'source': 'libvirt.LibvirtDriver'}],
        u'nodename': u'tianst.sh.intel.com',
        u'host': u'tianst',
        u'host_id': u'10.0.1.1'},
    u'priority': u'INFO',
    u'_context_is_admin': True,
    u'_context_user': None,
    u'publisher_id': u'compute.tianst.sh.intel.com',
    u'message_id': u'6eccedba-120e-4db8-9735-2ad5f061e5ee',
    u'_context_remote_address': None,
    u'_context_roles': [],
    u'timestamp': u'2013-07-29 06:51:34.474815',
    u'_context_timestamp': u'2013-07-29T06:51:34.348091',
    u'_unique_id': u'0ee26117077648e18d88ac76e28a72e2',
    u'_context_project_name': None,
    u'_context_read_deleted': u'no',
    u'_context_tenant': None,
    u'_context_instance_lock_checked': False,
    u'_context_project_id': None,
    u'_context_user_name': None
}

RES_ID = '%s_%s' % (METRICS_UPDATE['payload']['host'],
                    METRICS_UPDATE['payload']['nodename'])


class TestMetricsNotifications(test.BaseTestCase):
    def _process_notification(self, ic):
        self.assertIn(METRICS_UPDATE['event_type'],
                      ic.event_types)
        samples = list(ic.process_notification(METRICS_UPDATE))
        self.assertEqual(samples[0].resource_id, RES_ID)
        return samples[0]

    def test_compute_metrics(self):
        ERROR_METRICS = copy.copy(METRICS_UPDATE)
        ERROR_METRICS['payload'] = {"metric_err": []}
        ic = cpu.CpuFrequency()
        info = ic._get_sample(METRICS_UPDATE, 'cpu.frequency')
        info_none = ic._get_sample(METRICS_UPDATE, 'abc.efg')
        info_error = ic._get_sample(ERROR_METRICS, 'cpu.frequency')
        self.assertEqual(info['payload']['name'], 'cpu.frequency')
        self.assertIsNone(info_none)
        self.assertIsNone(info_error)

    def test_compute_cpu_frequency(self):
        c = self._process_notification(cpu.CpuFrequency())
        self.assertEqual(c.name, 'compute.node.cpu.frequency')
        self.assertEqual(c.volume, 1600)

    def test_compute_cpu_user_time(self):
        c = self._process_notification(cpu.CpuUserTime())
        self.assertEqual(c.name, 'compute.node.cpu.user.time')
        self.assertEqual(c.volume, 17421440000000L)

    def test_compute_cpu_kernel_time(self):
        c = self._process_notification(cpu.CpuKernelTime())
        self.assertEqual(c.name, 'compute.node.cpu.kernel.time')
        self.assertEqual(c.volume, 7852600000000L)

    def test_compute_cpu_idle_time(self):
        c = self._process_notification(cpu.CpuIdleTime())
        self.assertEqual(c.name, 'compute.node.cpu.idle.time')
        self.assertEqual(c.volume, 1307374400000000L)

    def test_compute_cpu_iowait_time(self):
        c = self._process_notification(cpu.CpuIowaitTime())
        self.assertEqual(c.name, 'compute.node.cpu.iowait.time')
        self.assertEqual(c.volume, 11697470000000L)

    def test_compute_cpu_kernel_percent(self):
        c = self._process_notification(cpu.CpuKernelPercent())
        self.assertEqual(c.name, 'compute.node.cpu.kernel.percent')
        self.assertEqual(c.volume, 0.5841204961898534)

    def test_compute_cpu_idle_percent(self):
        c = self._process_notification(cpu.CpuIdlePercent())
        self.assertEqual(c.name, 'compute.node.cpu.idle.percent')
        self.assertEqual(c.volume, 97.24985141658965)

    def test_compute_cpu_user_percent(self):
        c = self._process_notification(cpu.CpuUserPercent())
        self.assertEqual(c.name, 'compute.node.cpu.user.percent')
        self.assertEqual(c.volume, 1.2959045637294348)

    def test_compute_cpu_iowait_percent(self):
        c = self._process_notification(cpu.CpuIowaitPercent())
        self.assertEqual(c.name, 'compute.node.cpu.iowait.percent')
        self.assertEqual(c.volume, 0.8701235234910634)

    def test_compute_cpu_percent(self):
        c = self._process_notification(cpu.CpuPercent())
        self.assertEqual(c.name, 'compute.node.cpu.percent')
        self.assertEqual(c.volume, 2.7501485834103515)
