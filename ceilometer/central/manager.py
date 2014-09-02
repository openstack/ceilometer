#
# Copyright 2012-2013 eNovance <licensing@enovance.com>
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

from ceilometer import agent
from ceilometer.openstack.common import log

OPTS = [
    cfg.StrOpt('partitioning_group_prefix',
               default=None,
               help='Work-load partitioning group prefix. Use only if you '
                    'want to run multiple central agents with different '
                    'config files. For each sub-group of the central agent '
                    'pool with the same partitioning_group_prefix a disjoint '
                    'subset of pollsters should be loaded.'),
]
cfg.CONF.register_opts(OPTS, group='central')
cfg.CONF.import_group('service_credentials', 'ceilometer.service')

LOG = log.getLogger(__name__)


class AgentManager(agent.AgentManager):

    def __init__(self):
        super(AgentManager, self).__init__(
            'central', group_prefix=cfg.CONF.central.partitioning_group_prefix)

    def interval_task(self, task):
        try:
            self.keystone = ksclient.Client(
                username=cfg.CONF.service_credentials.os_username,
                password=cfg.CONF.service_credentials.os_password,
                tenant_id=cfg.CONF.service_credentials.os_tenant_id,
                tenant_name=cfg.CONF.service_credentials.os_tenant_name,
                cacert=cfg.CONF.service_credentials.os_cacert,
                auth_url=cfg.CONF.service_credentials.os_auth_url,
                region_name=cfg.CONF.service_credentials.os_region_name,
                insecure=cfg.CONF.service_credentials.insecure)
        except Exception as e:
            self.keystone = e

        super(AgentManager, self).interval_task(task)
