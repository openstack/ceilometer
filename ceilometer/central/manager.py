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

from ceilometer import agent
from ceilometer import extension_manager
from ceilometer.openstack.common import cfg
from ceilometer import service  # For cfg.CONF.os_*

OPTS = [
    cfg.ListOpt('disabled_central_pollsters',
                default=[],
                help='list of central pollsters to disable',
                ),
]

cfg.CONF.register_opts(OPTS)


class AgentManager(agent.AgentManager):

    def __init__(self):
        super(AgentManager, self).__init__(
            extension_manager.ActivatedExtensionManager(
                namespace='ceilometer.poll.central',
                disabled_names=cfg.CONF.disabled_central_pollsters,
            ),
        )

    def periodic_tasks(self, context, raise_on_error=False):
        """Tasks to be run at a periodic interval."""
        self.keystone = ksclient.Client(username=cfg.CONF.os_username,
                                        password=cfg.CONF.os_password,
                                        tenant_id=cfg.CONF.os_tenant_id,
                                        tenant_name=cfg.CONF.os_tenant_name,
                                        auth_url=cfg.CONF.os_auth_url)

        self.pollster_manager.map(self.publish_counters_from_one_pollster,
                                  manager=self,
                                  context=context,
                                  )
