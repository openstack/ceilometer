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

from oslo_config import cfg
from oslo_utils import timeutils
import six

from ceilometer.agent import plugin_base
from ceilometer.i18n import _
from ceilometer.ipmi.platform import exception as nmexcept
from ceilometer.ipmi.platform import intel_node_manager as node_manager
from ceilometer.openstack.common import log
from ceilometer import sample

CONF = cfg.CONF
CONF.import_opt('host', 'ceilometer.service')
CONF.import_opt('polling_retry', 'ceilometer.ipmi.pollsters',
                group='ipmi')

LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class _Base(plugin_base.PollsterBase):

    def setup_environment(self):
        super(_Base, self).setup_environment()
        self.nodemanager = node_manager.NodeManager()
        self.polling_failures = 0

        # Do not load this extension if no NM support
        if not self.nodemanager.nm_support:
            raise plugin_base.ExtensionLoadError()

    @property
    def default_discovery(self):
        return 'local_node'

    @abc.abstractmethod
    def read_data(self):
        """Return data sample for IPMI."""

    def get_samples(self, manager, cache, resources):
        # Only one resource for Node Manager pollster
        try:
            stats = self.read_data()
        except nmexcept.IPMIException:
            self.polling_failures += 1
            LOG.warning(_('Polling %(name)s faild for %(cnt)s times!')
                        % ({'name': self.NAME,
                            'cnt': self.polling_failures}))
            if (CONF.ipmi.polling_retry >= 0 and
                    self.polling_failures > CONF.ipmi.polling_retry):
                LOG.warning(_('Pollster for %s is disabled!') % self.NAME)
                raise plugin_base.PollsterPermanentError(resources[0])
            else:
                return

        self.polling_failures = 0

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
