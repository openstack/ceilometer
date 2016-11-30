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

import abc

from oslo_log import log
import six

from ceilometer.agent import plugin_base
from ceilometer.i18n import _
from ceilometer.ipmi.platform import exception as nmexcept
from ceilometer.ipmi.platform import intel_node_manager as node_manager
from ceilometer import sample

LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class _Base(plugin_base.PollsterBase):

    def setup_environment(self):
        super(_Base, self).setup_environment()
        self.nodemanager = node_manager.NodeManager(self.conf)
        self.polling_failures = 0

        # Do not load this extension if no NM support
        if self.nodemanager.nm_version == 0:
            raise plugin_base.ExtensionLoadError()

    @property
    def default_discovery(self):
        return 'local_node'

    def get_value(self, stats):
        """Get value from statistics."""
        return node_manager._hex(stats["Current_value"])

    @abc.abstractmethod
    def read_data(self, cache):
        """Return data sample for IPMI."""

    def get_samples(self, manager, cache, resources):
        # Only one resource for Node Manager pollster
        try:
            stats = self.read_data(cache)
        except nmexcept.IPMIException:
            self.polling_failures += 1
            LOG.warning(_('Polling %(name)s failed for %(cnt)s times!')
                        % ({'name': self.NAME,
                            'cnt': self.polling_failures}))
            if 0 <= self.conf.ipmi.polling_retry < self.polling_failures:
                LOG.warning(_('Pollster for %s is disabled!') % self.NAME)
                raise plugin_base.PollsterPermanentError(resources)
            else:
                return

        self.polling_failures = 0

        metadata = {
            'node': self.conf.host
        }

        if stats:
            data = self.get_value(stats)

            yield sample.Sample(
                name=self.NAME,
                type=self.TYPE,
                unit=self.UNIT,
                volume=data,
                user_id=None,
                project_id=None,
                resource_id=self.conf.host,
                resource_metadata=metadata)


class InletTemperaturePollster(_Base):
    # Note(ildikov): The new meter name should be
    # "hardware.ipmi.node.inlet_temperature". As currently there
    # is no meter deprecation support in the code, we should use the
    # old name in order to avoid confusion.
    NAME = "hardware.ipmi.node.temperature"
    TYPE = sample.TYPE_GAUGE
    UNIT = "C"

    def read_data(self, cache):
        return self.nodemanager.read_inlet_temperature()


class OutletTemperaturePollster(_Base):
    NAME = "hardware.ipmi.node.outlet_temperature"
    TYPE = sample.TYPE_GAUGE
    UNIT = "C"

    def read_data(self, cache):
        return self.nodemanager.read_outlet_temperature()


class PowerPollster(_Base):
    NAME = "hardware.ipmi.node.power"
    TYPE = sample.TYPE_GAUGE
    UNIT = "W"

    def read_data(self, cache):
        return self.nodemanager.read_power_all()


class AirflowPollster(_Base):
    NAME = "hardware.ipmi.node.airflow"
    TYPE = sample.TYPE_GAUGE
    UNIT = "CFM"

    def read_data(self, cache):
        return self.nodemanager.read_airflow()


class CUPSIndexPollster(_Base):
    NAME = "hardware.ipmi.node.cups"
    TYPE = sample.TYPE_GAUGE
    UNIT = "CUPS"

    def read_data(self, cache):
        return self.nodemanager.read_cups_index()

    def get_value(self, stats):
        return node_manager._hex(stats["CUPS_Index"])


class _CUPSUtilPollsterBase(_Base):
    CACHE_KEY_CUPS = 'CUPS'

    def read_data(self, cache):
        i_cache = cache.setdefault(self.CACHE_KEY_CUPS, {})
        if not i_cache:
            i_cache.update(self.nodemanager.read_cups_utilization())
        return i_cache


class CPUUtilPollster(_CUPSUtilPollsterBase):
    NAME = "hardware.ipmi.node.cpu_util"
    TYPE = sample.TYPE_GAUGE
    UNIT = "%"

    def get_value(self, stats):
        return node_manager._hex(stats["CPU_Utilization"])


class MemUtilPollster(_CUPSUtilPollsterBase):
    NAME = "hardware.ipmi.node.mem_util"
    TYPE = sample.TYPE_GAUGE
    UNIT = "%"

    def get_value(self, stats):
        return node_manager._hex(stats["Mem_Utilization"])


class IOUtilPollster(_CUPSUtilPollsterBase):
    NAME = "hardware.ipmi.node.io_util"
    TYPE = sample.TYPE_GAUGE
    UNIT = "%"

    def get_value(self, stats):
        return node_manager._hex(stats["IO_Utilization"])
