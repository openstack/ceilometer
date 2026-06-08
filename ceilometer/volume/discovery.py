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

from ceilometer import cinder_client
from ceilometer.polling import plugin_base


class _BaseDiscovery(plugin_base.DiscoveryBase):
    def __init__(self, conf):
        super().__init__(conf)
        self.client = cinder_client.Client(conf)


class VolumeDiscovery(_BaseDiscovery):
    def discover(self, manager, param=None):
        """Discover volume resources to monitor."""

        return self.client.list_volumes(search_opts={'all_tenants': True})


class VolumeSnapshotsDiscovery(_BaseDiscovery):
    def discover(self, manager, param=None):
        """Discover snapshot resources to monitor."""

        return self.client.list_volume_snapshots(
            search_opts={'all_tenants': True})


class VolumeBackupsDiscovery(_BaseDiscovery):
    def discover(self, manager, param=None):
        """Discover volume resources to monitor."""

        return self.client.list_backups(search_opts={'all_tenants': True})


class VolumePoolsDiscovery(_BaseDiscovery):
    def discover(self, manager, param=None):
        """Discover volume resources to monitor."""

        return self.client.list_pools(detailed=True)


class VolumeServicesDiscovery(_BaseDiscovery):
    def discover(self, manager, param=None):
        """Discover cinder service resources to monitor."""

        return self.client.list_services()
