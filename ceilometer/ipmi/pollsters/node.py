# Copyright 2014 Intel
#
# Author: Zhai Edwin <edwin.zhai@intel.com>
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

import abc

from oslo.config import cfg
from oslo.utils import timeutils
import six

from ceilometer.ipmi.platform import intel_node_manager as node_manager
from ceilometer import plugin
from ceilometer import sample

CONF = cfg.CONF
CONF.import_opt('host', 'ceilometer.service')


@six.add_metaclass(abc.ABCMeta)
class _Base(plugin.PollsterBase):
    def __init__(self):
        self.nodemanager = node_manager.NodeManager()

    @property
    def default_discovery(self):
        return None

    @abc.abstractmethod
    def read_data(self):
        """Return data sample for IPMI."""

    def get_samples(self, manager, cache, resources):
        stats = self.read_data()

        metadata = {
            'node': CONF.host
        }

        if stats:
            data = node_manager._hex(stats["Current_value"])

            yield sample.Sample(
                name=self.NAME,
                type=self.TYPE,
                unit=self.UNIT,
                volume=data,
                user_id=None,
                project_id=None,
                resource_id=CONF.host,
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata=metadata)


class TemperaturePollster(_Base):
    NAME = "hardware.ipmi.node.temperature"
    TYPE = sample.TYPE_GAUGE
    UNIT = "C"

    def read_data(self):
        return self.nodemanager.read_temperature_all()


class PowerPollster(_Base):
    NAME = "hardware.ipmi.node.power"
    TYPE = sample.TYPE_GAUGE
    UNIT = "W"

    def read_data(self):
        return self.nodemanager.read_power_all()
