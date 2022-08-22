# Copyright (C) 2014 eNovance SAS <licensing@enovance.com>
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

from unittest import mock

from oslotest import base

from ceilometer import neutron_client
from ceilometer import service


class TestNeutronClient(base.BaseTestCase):

    def setUp(self):
        super(TestNeutronClient, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.nc = neutron_client.Client(self.CONF)
        self.nc.lb_version = 'v1'

    @staticmethod
    def fake_ports_list():
        return {'ports':
                [{'admin_state_up': True,
                  'device_id': '674e553b-8df9-4321-87d9-93ba05b93558',
                  'device_owner': 'network:router_gateway',
                  'extra_dhcp_opts': [],
                  'id': '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                  'mac_address': 'fa:16:3e:c5:35:93',
                  'name': '',
                  'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                  'status': 'ACTIVE',
                  'tenant_id': '89271fa581ab4380bf172f868c3615f9'},
                 ]}

    def test_port_get_all(self):
        with mock.patch.object(self.nc.client, 'list_ports',
                               side_effect=self.fake_ports_list):
            ports = self.nc.port_get_all()

        self.assertEqual(1, len(ports))
        self.assertEqual('96d49cc3-4e01-40ce-9cac-c0e32642a442',
                         ports[0]['id'])

    @staticmethod
    def fake_networks_list():
        return {'networks':
                [{'admin_state_up': True,
                  'id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                  'name': 'public',
                  'provider:network_type': 'gre',
                  'provider:physical_network': None,
                  'provider:segmentation_id': 2,
                  'router:external': True,
                  'shared': False,
                  'status': 'ACTIVE',
                  'subnets': ['c4b6f5b8-3508-4896-b238-a441f25fb492'],
                  'tenant_id': '62d6f08bbd3a44f6ad6f00ca15cce4e5'},
                 ]}
