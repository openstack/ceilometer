#
# Copyright 2012-2013 eNovance <licensing@enovance.com>
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

from oslo_config import cfg

from ceilometer.agent import base
from ceilometer import keystone_client
from ceilometer.openstack.common import log

OPTS = [
    cfg.StrOpt('partitioning_group_prefix',
               default=None,
               deprecated_group='central',
               help='Work-load partitioning group prefix. Use only if you '
                    'want to run multiple polling agents with different '
                    'config files. For each sub-group of the agent '
                    'pool with the same partitioning_group_prefix a disjoint '
                    'subset of pollsters should be loaded.'),
]

cfg.CONF.register_opts(OPTS, group='polling')

LOG = log.getLogger(__name__)


class AgentManager(base.AgentManager):

    def __init__(self, namespaces=None, pollster_list=None):
        namespaces = namespaces or ['compute', 'central']
        pollster_list = pollster_list or []
        super(AgentManager, self).__init__(
            namespaces, pollster_list,
            group_prefix=cfg.CONF.polling.partitioning_group_prefix)

    def interval_task(self, task):
        try:
            self.keystone = keystone_client.get_client()
        except Exception as e:
            self.keystone = e
        super(AgentManager, self).interval_task(task)
