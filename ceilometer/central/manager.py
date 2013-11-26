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

from keystoneclient.v2_0 import client as ksclient
from oslo.config import cfg
from stevedore import extension

from ceilometer import agent
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import service as os_service
from ceilometer import service

cfg.CONF.import_group('service_credentials', 'ceilometer.service')

LOG = log.getLogger(__name__)


class PollingTask(agent.PollingTask):
    def poll_and_publish(self):
        """Tasks to be run at a periodic interval."""
        with self.publish_context as publisher:
            # TODO(yjiang5) passing samples into get_samples to avoid
            # polling all counters one by one
            cache = {}
            for pollster in self.pollsters:
                try:
                    LOG.info(_("Polling pollster %s"), pollster.name)
                    resources = list(self.resources[pollster.name])
                    samples = list(pollster.obj.get_samples(
                        self.manager,
                        cache,
                        resources=resources,
                    ))
                    publisher(samples)
                except Exception as err:
                    LOG.warning(_(
                        'Continue after error from %(name)s: %(error)s')
                        % ({'name': pollster.name, 'error': err}))
                    LOG.exception(err)


class AgentManager(agent.AgentManager):

    def __init__(self):
        super(AgentManager, self).__init__(
            extension.ExtensionManager(
                namespace='ceilometer.poll.central',
                invoke_on_load=True,
            )
        )

    def create_polling_task(self):
        return PollingTask(self)

    def interval_task(self, task):
        self.keystone = ksclient.Client(
            username=cfg.CONF.service_credentials.os_username,
            password=cfg.CONF.service_credentials.os_password,
            tenant_id=cfg.CONF.service_credentials.os_tenant_id,
            tenant_name=cfg.CONF.service_credentials.os_tenant_name,
            cacert=cfg.CONF.service_credentials.os_cacert,
            auth_url=cfg.CONF.service_credentials.os_auth_url,
            region_name=cfg.CONF.service_credentials.os_region_name,
            insecure=cfg.CONF.service_credentials.insecure)

        super(AgentManager, self).interval_task(task)


def agent_central():
    service.prepare_service()
    os_service.launch(AgentManager()).wait()
