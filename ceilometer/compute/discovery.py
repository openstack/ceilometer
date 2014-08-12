#
# Copyright 2014 Red Hat, Inc
#
# Author: Eoghan Glynn <eglynn@redhat.com>
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

from ceilometer import nova_client
from ceilometer import plugin

OPTS = [
    cfg.BoolOpt('workload_partitioning',
                default=False,
                help='Enable work-load partitioning, allowing multiple '
                     'compute agents to be run simultaneously.')
]
cfg.CONF.register_opts(OPTS, group='compute')


class InstanceDiscovery(plugin.DiscoveryBase):
    def __init__(self):
        super(InstanceDiscovery, self).__init__()
        self.nova_cli = nova_client.Client()

    def discover(self, param=None):
        """Discover resources to monitor."""
        instances = self.nova_cli.instance_get_all_by_host(cfg.CONF.host)
        return [i for i in instances
                if getattr(i, 'OS-EXT-STS:vm_state', None) != 'error']

    @property
    def group_id(self):
        if cfg.CONF.compute.workload_partitioning:
            return cfg.CONF.host
        else:
            return None
