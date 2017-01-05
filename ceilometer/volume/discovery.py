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

from cinderclient import client as cinder_client
from oslo_config import cfg

from ceilometer.agent import plugin_base
from ceilometer import keystone_client

SERVICE_OPTS = [
    cfg.StrOpt('cinder', deprecated_name='cinderv2',
               default='volumev3',
               help='Cinder service type.'),
]


class _BaseDiscovery(plugin_base.DiscoveryBase):
    def __init__(self, conf):
        super(_BaseDiscovery, self).__init__(conf)
        creds = conf.service_credentials
        self.client = cinder_client.Client(
            version='3',
            session=keystone_client.get_session(conf),
            region_name=creds.region_name,
            interface=creds.interface,
            service_type=conf.service_types.cinder
        )


class VolumeDiscovery(_BaseDiscovery):
    def discover(self, manager, param=None):
        """Discover volume resources to monitor."""

        return self.client.volumes.list(search_opts={'all_tenants': True})


class VolumeSnapshotsDiscovery(_BaseDiscovery):
    def discover(self, manager, param=None):
        """Discover snapshot resources to monitor."""

        return self.client.volume_snapshots.list(
            search_opts={'all_tenants': True})


class VolumeBackupsDiscovery(_BaseDiscovery):
    def discover(self, manager, param=None):
        """Discover volume resources to monitor."""

        return self.client.backups.list(search_opts={'all_tenants': True})
