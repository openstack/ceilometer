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

from ceilometer import designate_client
from ceilometer.polling import plugin_base


class ZoneDiscovery(plugin_base.DiscoveryBase):
    """Discovery class for Designate DNS zones."""

    KEYSTONE_REQUIRED_FOR_SERVICE = 'designate'

    def __init__(self, conf):
        super().__init__(conf)
        self.designate_client = designate_client.Client(conf)

    def discover(self, manager, param=None):
        """Discover DNS zone resources to monitor."""
        return self.designate_client.zones_list()
