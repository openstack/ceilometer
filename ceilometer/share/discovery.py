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

from ceilometer import manila_client
from ceilometer.polling import plugin_base


class ShareDiscovery(plugin_base.DiscoveryBase):
    """Discovery class for Manila shares."""

    KEYSTONE_REQUIRED_FOR_SERVICE = 'manila'

    def __init__(self, conf):
        super().__init__(conf)
        self.manila_client = manila_client.Client(conf)

    def discover(self, manager, param=None):
        """Discover share resources to monitor."""
        return self.manila_client.shares_list()
