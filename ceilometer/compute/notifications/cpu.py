# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Intel
#
# Author: Shuangtai Tian <shuangtai.tian@intel.com>
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
"""Converters for producing compute CPU sample messages from notification
events.
"""

from ceilometer.compute import notifications
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer import sample

LOG = log.getLogger(__name__)


class ComputeMetricsNotificationBase(notifications.ComputeNotificationBase):
    """Convert compute.metrics.update notifications into Samples
    """
    event_types = ['compute.metrics.update']
    metric = None
    sample_type = None
    unit = None

    @staticmethod
    def _get_sample(message, name):
        try:
            for metric in message['payload']['metrics']:
                if name == metric['name']:
                    info = {}
                    info['payload'] = metric
                    info['event_type'] = message['event_type']
                    info['publisher_id'] = message['publisher_id']
                    info['resource_id'] = '%s_%s' % (
                        message['payload']['host'],
                        message['payload']['nodename'])
                    info['timestamp'] = str(timeutils.parse_strtime(
                        metric['timestamp']))
                    return info
        except Exception as err:
            LOG.warning(_('An error occurred while building %(m)s '
                          'sample: %(e)s') % {'m': name, 'e': err})

    def process_notification(self, message):
        info = self._get_sample(message, self.metric)
        if info:
            yield sample.Sample.from_notification(
                name='compute.node.%s' % self.metric,
                type=self.sample_type,
                unit=self.unit,
                volume=(info['payload']['value'] * 100 if self.unit == '%'
                        else info['payload']['value']),
                user_id=None,
                project_id=None,
                resource_id=info['resource_id'],
                message=info)


class CpuFrequency(ComputeMetricsNotificationBase):
    """Handle CPU current frequency message."""
    metric = 'cpu.frequency'
    sample_type = sample.TYPE_GAUGE,
    unit = 'MHz'


class CpuUserTime(ComputeMetricsNotificationBase):
    """Handle CPU user mode time message."""
    metric = 'cpu.user.time'
    sample_type = sample.TYPE_CUMULATIVE,
    unit = 'ns'


class CpuKernelTime(ComputeMetricsNotificationBase):
    """Handle CPU kernel time message."""
    metric = 'cpu.kernel.time'
    unit = 'ns'
    sample_type = sample.TYPE_CUMULATIVE,


class CpuIdleTime(ComputeMetricsNotificationBase):
    """Handle CPU idle time message."""
    metric = 'cpu.idle.time'
    unit = 'ns'
    sample_type = sample.TYPE_CUMULATIVE,


class CpuIowaitTime(ComputeMetricsNotificationBase):
    """Handle CPU I/O wait time message."""
    metric = 'cpu.iowait.time'
    unit = 'ns'
    sample_type = sample.TYPE_CUMULATIVE,


class CpuKernelPercent(ComputeMetricsNotificationBase):
    """Handle CPU kernel percentage message."""
    metric = 'cpu.kernel.percent'
    unit = '%'
    sample_type = sample.TYPE_GAUGE,


class CpuIdlePercent(ComputeMetricsNotificationBase):
    """Handle CPU idle percentage message."""
    metric = 'cpu.idle.percent'
    unit = '%'
    sample_type = sample.TYPE_GAUGE,


class CpuUserPercent(ComputeMetricsNotificationBase):
    """Handle CPU user mode percentage message."""
    metric = 'cpu.user.percent'
    unit = '%'
    sample_type = sample.TYPE_GAUGE,


class CpuIowaitPercent(ComputeMetricsNotificationBase):
    """Handle CPU I/O wait percentage message."""
    metric = 'cpu.iowait.percent'
    unit = '%'
    sample_type = sample.TYPE_GAUGE,


class CpuPercent(ComputeMetricsNotificationBase):
    """Handle generic CPU utilization message."""
    metric = 'cpu.percent'
    unit = '%'
    sample_type = sample.TYPE_GAUGE,
