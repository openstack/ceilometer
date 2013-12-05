# -*- encoding: utf-8 -*-
#
# Copyright © 2012-2013 eNovance <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
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

from oslo.config import cfg
from stevedore import extension

from ceilometer import agent
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer import nova_client
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import service as os_service
from ceilometer import service

LOG = log.getLogger(__name__)


class PollingTask(agent.PollingTask):
    def poll_and_publish_instances(self, instances):
        with self.publish_context as publisher:
            for instance in instances:
                if getattr(instance, 'OS-EXT-STS:vm_state', None) == 'error':
                    continue
                cache = {}
                for pollster in self.pollsters:
                    try:
                        LOG.info(_("Polling pollster %s"), pollster.name)
                        samples = list(pollster.obj.get_samples(
                            self.manager,
                            cache,
                            instance,
                        ))
                        publisher(samples)
                    except Exception as err:
                        LOG.warning(_(
                            'Continue after error from %(name)s: %(error)s')
                            % ({'name': pollster.name, 'error': err}))
                        LOG.exception(err)

    def poll_and_publish(self):
        try:
            instances = self.manager.nv.instance_get_all_by_host(cfg.CONF.host)
        except Exception as err:
            LOG.exception(_('Unable to retrieve instances: %s') % err)
        else:
            self.poll_and_publish_instances(instances)


class AgentManager(agent.AgentManager):

    def __init__(self):
        super(AgentManager, self).__init__(
            extension.ExtensionManager(
                namespace='ceilometer.poll.compute',
                invoke_on_load=True,
            ),
        )
        self._inspector = virt_inspector.get_hypervisor_inspector()
        self.nv = nova_client.Client()

    def create_polling_task(self):
        return PollingTask(self)

    @property
    def inspector(self):
        return self._inspector


def agent_compute():
    service.prepare_service()
    os_service.launch(AgentManager()).wait()
