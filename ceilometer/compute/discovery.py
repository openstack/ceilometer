#
# Copyright 2014 Red Hat, Inc
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
from oslo_utils import timeutils

from ceilometer.agent import plugin_base
from ceilometer import nova_client

OPTS = [
    cfg.BoolOpt('workload_partitioning',
                default=False,
                help='Enable work-load partitioning, allowing multiple '
                     'compute agents to be run simultaneously.'),
    cfg.IntOpt('resource_update_interval',
               default=0,
               min=0,
               help="New instances will be discovered periodically based"
                    " on this option (in seconds). By default, "
                    "the agent discovers instances according to pipeline "
                    "polling interval. If option is greater than 0, "
                    "the instance list to poll will be updated based "
                    "on this option's interval. Measurements relating "
                    "to the instances will match intervals "
                    "defined in pipeline.")
]
cfg.CONF.register_opts(OPTS, group='compute')


class InstanceDiscovery(plugin_base.DiscoveryBase):
    def __init__(self):
        super(InstanceDiscovery, self).__init__()
        self.nova_cli = nova_client.Client()
        self.last_run = None
        self.instances = {}
        self.expiration_time = cfg.CONF.compute.resource_update_interval

    def discover(self, manager, param=None):
        """Discover resources to monitor."""
        secs_from_last_update = 0
        if self.last_run:
            secs_from_last_update = timeutils.delta_seconds(
                self.last_run, timeutils.utcnow(True))

        instances = []
        # NOTE(ityaptin) we update make a nova request only if
        # it's a first discovery or resources expired
        if not self.last_run or secs_from_last_update >= self.expiration_time:
            try:
                utc_now = timeutils.utcnow(True)
                since = self.last_run.isoformat() if self.last_run else None
                instances = self.nova_cli.instance_get_all_by_host(
                    cfg.CONF.host, since)
                self.last_run = utc_now
            except Exception:
                # NOTE(zqfan): instance_get_all_by_host is wrapped and will log
                # exception when there is any error. It is no need to raise it
                # again and print one more time.
                return []

        for instance in instances:
            if getattr(instance, 'OS-EXT-STS:vm_state', None) in ['deleted',
                                                                  'error']:
                self.instances.pop(instance.id, None)
            else:
                self.instances[instance.id] = instance

        return self.instances.values()

    @property
    def group_id(self):
        if cfg.CONF.compute.workload_partitioning:
            return cfg.CONF.host
        else:
            return None
