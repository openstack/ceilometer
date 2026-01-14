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
from oslo_config import cfg

from ceilometer import keystone_client

SERVICE_OPTS = [
    cfg.StrOpt('octavia',
               default='load-balancer',
               help='Octavia service type.'),
]


class Client:
    """A client which gets information via openstacksdk."""

    def __init__(self, conf):
        """Initialize an Octavia client object."""
        creds = conf.service_credentials

        self.conn = openstack.connection.Connection(
            session=keystone_client.get_session(conf),
            region_name=creds.region_name,
            load_balancer_interface=creds.interface,
            load_balancer_service_type=conf.service_types.octavia
        )

    def loadbalancers_list(self):
        """Return a list of load balancers."""
        return self.conn.load_balancer.load_balancers()
