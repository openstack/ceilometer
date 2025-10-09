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

import openstack

from ceilometer import keystone_client
from ceilometer.polling import plugin_base


class ImagesDiscovery(plugin_base.DiscoveryBase):
    def __init__(self, conf):
        super().__init__(conf)
        creds = conf.service_credentials
        self.image_client = openstack.connection.Connection(
            image_api_version='2',
            session=keystone_client.get_session(conf),
            region_name=creds.region_name,
            image_interface=creds.interface)

    def discover(self, manager, param=None):
        """Discover resources to monitor."""
        return self.image_client.image.images()
