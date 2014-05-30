# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Julien Danjou <julien@danjou.info>
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
"""Tests for ceilometer.network.notifications
"""

from ceilometer.network import notifications
from ceilometer.openstack.common import test

NOTIFICATION_NETWORK_CREATE = {
    u'_context_roles': [u'anotherrole',
                        u'Member'],
    u'_context_read_deleted': u'no',
    u'event_type': u'network.create.end',
    u'timestamp': u'2012-09-27 14:11:27.086575',
    u'_context_tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
    u'payload': {u'network':
                 {u'status': u'ACTIVE',
                  u'subnets': [],
                  u'name': u'abcedf',
                  u'router:external': False,
                  u'tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
                  u'admin_state_up': True,
                  u'shared': False,
                  u'id': u'7fd4eb2f-a38e-4c25-8490-71ca8800c9be'}},
    u'priority': u'INFO',
    u'_context_is_admin': False,
    u'_context_timestamp': u'2012-09-27 14:11:26.924779',
    u'_context_user_id': u'b44b7ce67fc84414a5c1660a92a1b862',
    u'publisher_id': u'network.ubuntu-VirtualBox',
    u'message_id': u'9e839576-cc47-4c60-a7d8-5743681213b1'}

NOTIFICATION_BULK_NETWORK_CREATE = {
    '_context_roles': [u'_member_',
                       u'heat_stack_owner',
                       u'admin'],
    u'_context_request_id': u'req-a2dfdefd-b773-4400-9d52-5e146e119950',
    u'_context_read_deleted': u'no',
    u'event_type': u'network.create.end',
    u'_context_user_name': u'admin',
    u'_context_project_name': u'admin',
    u'timestamp': u'2014-05-1510: 24: 56.335612',
    u'_context_tenant_id': u'980ec4870033453ead65c0470a78b8a8',
    u'_context_tenant_name': u'admin',
    u'_context_tenant': u'980ec4870033453ead65c0470a78b8a8',
    u'message_id': u'914eb601-9390-4a72-8629-f013a4c84467',
    u'priority': 'info',
    u'_context_is_admin': True,
    u'_context_project_id': u'980ec4870033453ead65c0470a78b8a8',
    u'_context_timestamp': u'2014-05-1510: 24: 56.285975',
    u'_context_user': u'7520940056d54cceb25cbce888300bea',
    u'_context_user_id': u'7520940056d54cceb25cbce888300bea',
    u'publisher_id': u'network.devstack',
    u'payload': {
        u'networks': [{u'status': u'ACTIVE',
                       u'subnets': [],
                       u'name': u'test2',
                       u'provider: physical_network': None,
                       u'admin_state_up': True,
                       u'tenant_id': u'980ec4870033453ead65c0470a78b8a8',
                       u'provider: network_type': u'local',
                       u'shared': False,
                       u'id': u'7cbc7a66-bbd0-41fc-a186-81c3da5c9843',
                       u'provider: segmentation_id': None},
                      {u'status': u'ACTIVE',
                       u'subnets': [],
                       u'name': u'test3',
                       u'provider: physical_network': None,
                       u'admin_state_up': True,
                       u'tenant_id': u'980ec4870033453ead65c0470a78b8a8',
                       u'provider: network_type': u'local',
                       u'shared': False,
                       u'id': u'5a7cb86f-1638-4cc1-8dcc-8bbbc8c7510d',
                       u'provider: segmentation_id': None}]
    }
}

NOTIFICATION_SUBNET_CREATE = {
    u'_context_roles': [u'anotherrole',
                        u'Member'],
    u'_context_read_deleted': u'no',
    u'event_type': u'subnet.create.end',
    u'timestamp': u'2012-09-27 14:11:27.426620',
    u'_context_tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
    u'payload': {
        u'subnet': {
            u'name': u'mysubnet',
            u'enable_dhcp': True,
            u'network_id': u'7fd4eb2f-a38e-4c25-8490-71ca8800c9be',
            u'tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
            u'dns_nameservers': [],
            u'allocation_pools': [{u'start': u'192.168.42.2',
                                   u'end': u'192.168.42.254'}],
            u'host_routes': [],
            u'ip_version': 4,
            u'gateway_ip': u'192.168.42.1',
            u'cidr': u'192.168.42.0/24',
            u'id': u'1a3a170d-d7ce-4cc9-b1db-621da15a25f5'}},
    u'priority': u'INFO',
    u'_context_is_admin': False,
    u'_context_timestamp': u'2012-09-27 14:11:27.214490',
    u'_context_user_id': u'b44b7ce67fc84414a5c1660a92a1b862',
    u'publisher_id': u'network.ubuntu-VirtualBox',
    u'message_id': u'd86dfc66-d3c3-4aea-b06d-bf37253e6116'}

NOTIFICATION_BULK_SUBNET_CREATE = {
    '_context_roles': [u'_member_',
                       u'heat_stack_owner',
                       u'admin'],
    u'_context_request_id': u'req-b77e278a-0cce-4987-9f82-15957b234768',
    u'_context_read_deleted': u'no',
    u'event_type': u'subnet.create.end',
    u'_context_user_name': u'admin',
    u'_context_project_name': u'admin',
    u'timestamp': u'2014-05-1510: 47: 08.133888',
    u'_context_tenant_id': u'980ec4870033453ead65c0470a78b8a8',
    u'_context_tenant_name': u'admin',
    u'_context_tenant': u'980ec4870033453ead65c0470a78b8a8',
    u'message_id': u'c7e6f9fd-ead2-415f-8493-b95bedf72e43',
    u'priority': u'info',
    u'_context_is_admin': True,
    u'_context_project_id': u'980ec4870033453ead65c0470a78b8a8',
    u'_context_timestamp': u'2014-05-1510: 47: 07.970043',
    u'_context_user': u'7520940056d54cceb25cbce888300bea',
    u'_context_user_id': u'7520940056d54cceb25cbce888300bea',
    u'publisher_id': u'network.devstack',
    u'payload': {
        u'subnets': [{u'name': u'',
                      u'enable_dhcp': True,
                      u'network_id': u'3ddfe60b-34b4-4e9d-9440-43c904b1c58e',
                      u'tenant_id': u'980ec4870033453ead65c0470a78b8a8',
                      u'dns_nameservers': [],
                      u'ipv6_ra_mode': None,
                      u'allocation_pools': [{u'start': u'10.0.4.2',
                                             u'end': u'10.0.4.254'}],
                      u'host_routes': [],
                      u'ipv6_address_mode': None,
                      u'ip_version': 4,
                      u'gateway_ip': u'10.0.4.1',
                      u'cidr': u'10.0.4.0/24',
                      u'id': u'14020d7b-6dd7-4349-bb8e-8f954c919022'},
                     {u'name': u'',
                      u'enable_dhcp': True,
                      u'network_id': u'3ddfe60b-34b4-4e9d-9440-43c904b1c58e',
                      u'tenant_id': u'980ec4870033453ead65c0470a78b8a8',
                      u'dns_nameservers': [],
                      u'ipv6_ra_mode': None,
                      u'allocation_pools': [{u'start': u'10.0.5.2',
                                             u'end': u'10.0.5.254'}],
                      u'host_routes': [],
                      u'ipv6_address_mode': None,
                      u'ip_version': 4,
                      u'gateway_ip': u'10.0.5.1',
                      u'cidr': u'10.0.5.0/24',
                      u'id': u'a080991b-a32a-4bf7-a558-96c4b77d075c'}]
    }
}

NOTIFICATION_PORT_CREATE = {
    u'_context_roles': [u'anotherrole',
                        u'Member'],
    u'_context_read_deleted': u'no',
    u'event_type': u'port.create.end',
    u'timestamp': u'2012-09-27 14:28:31.536370',
    u'_context_tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
    u'payload': {
        u'port': {
            u'status': u'ACTIVE',
            u'name': u'',
            u'admin_state_up': True,
            u'network_id': u'7fd4eb2f-a38e-4c25-8490-71ca8800c9be',
            u'tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
            u'device_owner': u'',
            u'mac_address': u'fa:16:3e:75:0c:49',
            u'fixed_ips': [{
                u'subnet_id': u'1a3a170d-d7ce-4cc9-b1db-621da15a25f5',
                u'ip_address': u'192.168.42.3'}],
            u'id': u'9cdfeb92-9391-4da7-95a1-ca214831cfdb',
            u'device_id': u''}},
    u'priority': u'INFO',
    u'_context_is_admin': False,
    u'_context_timestamp': u'2012-09-27 14:28:31.438919',
    u'_context_user_id': u'b44b7ce67fc84414a5c1660a92a1b862',
    u'publisher_id': u'network.ubuntu-VirtualBox',
    u'message_id': u'7135b8ab-e13c-4ac8-bc31-75e7f756622a'}

NOTIFICATION_BULK_PORT_CREATE = {
    u'_context_roles': [u'_member_',
                        u'SwiftOperator'],
    u'_context_request_id': u'req-678be9ad-c399-475a-b3e8-8da0c06375aa',
    u'_context_read_deleted': u'no',
    u'event_type': u'port.create.end',
    u'_context_project_name': u'demo',
    u'timestamp': u'2014-05-0909: 19: 58.317548',
    u'_context_tenant_id': u'133087d90fc149528b501dd8b75ea965',
    u'_context_timestamp': u'2014-05-0909: 19: 58.160011',
    u'_context_tenant': u'133087d90fc149528b501dd8b75ea965',
    u'payload': {
        u'ports': [{u'status': u'DOWN',
                    u'name': u'port--1501135095',
                    u'allowed_address_pairs': [],
                    u'admin_state_up': True,
                    u'network_id': u'acf63fdc-b43b-475d-8cca-9429b843d5e8',
                    u'tenant_id': u'133087d90fc149528b501dd8b75ea965',
                    u'binding: vnic_type': u'normal',
                    u'device_owner': u'',
                    u'mac_address': u'fa: 16: 3e: 37: 10: 39',
                    u'fixed_ips': [],
                    u'id': u'296c2c9f-14e9-48da-979d-78b213454c59',
                    u'security_groups': [
                        u'a06f7c9d-9e5a-46b0-9f6c-ce812aa2e5ff'],
                    u'device_id': u''},
                   {u'status': u'DOWN',
                    u'name': u'',
                    u'allowed_address_pairs': [],
                    u'admin_state_up': False,
                    u'network_id': u'0a8eea59-0146-425c-b470-e9ddfa99ec61',
                    u'tenant_id': u'133087d90fc149528b501dd8b75ea965',
                    u'binding: vnic_type': u'normal',
                    u'device_owner': u'',
                    u'mac_address': u'fa: 16: 3e: 8e: 6e: 53',
                    u'fixed_ips': [],
                    u'id': u'd8bb667f-5cd3-4eca-a984-268e25b1b7a5',
                    u'security_groups': [
                        u'a06f7c9d-9e5a-46b0-9f6c-ce812aa2e5ff'],
                    u'device_id': u''}]
    },
    u'_unique_id': u'60b1650f17fc4fa59492f447321fb26c',
    u'_context_is_admin': False,
    u'_context_project_id': u'133087d90fc149528b501dd8b75ea965',
    u'_context_tenant_name': u'demo',
    u'_context_user': u'b1eb48f9c54741f4adc1b4ea512d400c',
    u'_context_user_name': u'demo',
    u'publisher_id': u'network.os-ci-test12',
    u'message_id': u'04aa45e1-3c30-4c69-8638-e7ff8621e9bc',
    u'_context_user_id': u'b1eb48f9c54741f4adc1b4ea512d400c',
    u'priority': u'INFO'
}

NOTIFICATION_PORT_UPDATE = {
    u'_context_roles': [u'anotherrole',
                        u'Member'],
    u'_context_read_deleted': u'no',
    u'event_type': u'port.update.end',
    u'timestamp': u'2012-09-27 14:35:09.514052',
    u'_context_tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
    u'payload': {
        u'port': {
            u'status': u'ACTIVE',
            u'name': u'bonjour',
            u'admin_state_up': True,
            u'network_id': u'7fd4eb2f-a38e-4c25-8490-71ca8800c9be',
            u'tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
            u'device_owner': u'',
            u'mac_address': u'fa:16:3e:75:0c:49',
            u'fixed_ips': [{
                u'subnet_id': u'1a3a170d-d7ce-4cc9-b1db-621da15a25f5',
                u'ip_address': u'192.168.42.3'}],
            u'id': u'9cdfeb92-9391-4da7-95a1-ca214831cfdb',
            u'device_id': u''}},
    u'priority': u'INFO',
    u'_context_is_admin': False,
    u'_context_timestamp': u'2012-09-27 14:35:09.447682',
    u'_context_user_id': u'b44b7ce67fc84414a5c1660a92a1b862',
    u'publisher_id': u'network.ubuntu-VirtualBox',
    u'message_id': u'07b0a3a1-c0b5-40ab-a09c-28dee6bf48f4'}


NOTIFICATION_NETWORK_EXISTS = {
    u'_context_roles': [u'anotherrole',
                        u'Member'],
    u'_context_read_deleted': u'no',
    u'event_type': u'network.exists',
    u'timestamp': u'2012-09-27 14:11:27.086575',
    u'_context_tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
    u'payload': {u'network':
                 {u'status': u'ACTIVE',
                  u'subnets': [],
                  u'name': u'abcedf',
                  u'router:external': False,
                  u'tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
                  u'admin_state_up': True,
                  u'shared': False,
                  u'id': u'7fd4eb2f-a38e-4c25-8490-71ca8800c9be'}},
    u'priority': u'INFO',
    u'_context_is_admin': False,
    u'_context_timestamp': u'2012-09-27 14:11:26.924779',
    u'_context_user_id': u'b44b7ce67fc84414a5c1660a92a1b862',
    u'publisher_id': u'network.ubuntu-VirtualBox',
    u'message_id': u'9e839576-cc47-4c60-a7d8-5743681213b1'}


NOTIFICATION_ROUTER_EXISTS = {
    u'_context_roles': [u'anotherrole',
                        u'Member'],
    u'_context_read_deleted': u'no',
    u'event_type': u'router.exists',
    u'timestamp': u'2012-09-27 14:11:27.086575',
    u'_context_tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
    u'payload': {u'router':
                 {'status': u'ACTIVE',
                  'external_gateway_info':
                  {'network_id': u'89d55642-4dec-43a4-a617-6cec051393b5'},
                  'name': u'router1',
                  'admin_state_up': True,
                  'tenant_id': u'bb04a2b769c94917b57ba49df7783cfd',
                  'id': u'ab8bb3ed-df23-4ca0-8f03-b887abcd5c23'}},
    u'priority': u'INFO',
    u'_context_is_admin': False,
    u'_context_timestamp': u'2012-09-27 14:11:26.924779',
    u'_context_user_id': u'b44b7ce67fc84414a5c1660a92a1b862',
    u'publisher_id': u'network.ubuntu-VirtualBox',
    u'message_id': u'9e839576-cc47-4c60-a7d8-5743681213b1'}


NOTIFICATION_FLOATINGIP_EXISTS = {
    u'_context_roles': [u'anotherrole',
                        u'Member'],
    u'_context_read_deleted': u'no',
    u'event_type': u'floatingip.exists',
    u'timestamp': u'2012-09-27 14:11:27.086575',
    u'_context_tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
    u'payload': {u'floatingip':
                 {'router_id': None,
                  'tenant_id': u'6e5f9df9b3a249ab834f25fe1b1b81fd',
                  'floating_network_id':
                  u'001400f7-1710-4245-98c3-39ba131cc39a',
                  'fixed_ip_address': None,
                  'floating_ip_address': u'172.24.4.227',
                  'port_id': None,
                  'id': u'2b7cc28c-6f78-4735-9246-257168405de6'}},
    u'priority': u'INFO',
    u'_context_is_admin': False,
    u'_context_timestamp': u'2012-09-27 14:11:26.924779',
    u'_context_user_id': u'b44b7ce67fc84414a5c1660a92a1b862',
    u'publisher_id': u'network.ubuntu-VirtualBox',
    u'message_id': u'9e839576-cc47-4c60-a7d8-5743681213b1'}


NOTIFICATION_FLOATINGIP_UPDATE = {
    u'_context_roles': [u'anotherrole',
                        u'Member'],
    u'_context_read_deleted': u'no',
    u'event_type': u'floatingip.update.start',
    u'timestamp': u'2012-09-27 14:11:27.086575',
    u'_context_tenant_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
    u'payload': {u'floatingip':
                   {u'fixed_ip_address': u'172.24.4.227',
                    u'id': u'a68c9390-829e-4732-bad4-e0a978498cc5',
                    u'port_id': u'e12150f2-885b-45bc-a248-af1c23787d55'}},
    u'priority': u'INFO',
    u'_unique_id': u'e483db017b2341fd9ec314dcda88d3e9',
    u'_context_is_admin': False,
    u'_context_project_id': u'82ed0c40ebe64d0bb3310027039c8ed2',
    u'_context_timestamp': u'2012-09-27 14:11:26.924779',
    u'_context_user_id': u'b44b7ce67fc84414a5c1660a92a1b862',
    u'publisher_id': u'network.ubuntu-VirtualBox',
    u'message_id': u'9e839576-cc47-4c60-a7d8-5743681213b1'}


NOTIFICATION_L3_METER = {
    u'_context_roles': [u'admin'],
    u'_context_read_deleted': u'no',
    u'event_type': u'l3.meter',
    u'timestamp': u'2013-08-22 13:14:06.880304',
    u'_context_tenant_id': None,
    u'payload': {u'first_update': 1377176476,
                 u'bytes': 0,
                 u'label_id': u'383244a7-e99b-433a-b4a1-d37cf5b17d15',
                 u'last_update': 1377177246,
                 u'host': u'precise64',
                 u'tenant_id': u'admin',
                 u'time': 30,
                 u'pkts': 0},
    u'priority': u'INFO',
    u'_context_is_admin': True,
    u'_context_timestamp': u'2013-08-22 13:01:06.614635',
    u'_context_user_id': None,
    u'publisher_id': u'metering.precise64',
    u'message_id': u'd7aee6e8-c7eb-4d47-9338-f60920d708e4',
    u'_unique_id': u'd5a3bdacdcc24644b84e67a4c10e886a',
    u'_context_project_id': None}


class TestNotifications(test.BaseTestCase):
    def test_network_create(self):
        v = notifications.Network()
        samples = list(v.process_notification(NOTIFICATION_NETWORK_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.create", samples[1].name)

    def test_bulk_network_create(self):
        v = notifications.Network()
        samples = list(v.process_notification(
            NOTIFICATION_BULK_NETWORK_CREATE))
        self.assertEqual(4, len(samples))
        self.assertEqual("network", samples[0].name)
        self.assertEqual("network.create", samples[1].name)
        self.assertEqual("network", samples[2].name)
        self.assertEqual("network.create", samples[3].name)

    def test_subnet_create(self):
        v = notifications.Subnet()
        samples = list(v.process_notification(NOTIFICATION_SUBNET_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("subnet.create", samples[1].name)

    def test_bulk_subnet_create(self):
        v = notifications.Subnet()
        samples = list(v.process_notification(NOTIFICATION_BULK_SUBNET_CREATE))
        self.assertEqual(4, len(samples))
        self.assertEqual("subnet", samples[0].name)
        self.assertEqual("subnet.create", samples[1].name)
        self.assertEqual("subnet", samples[2].name)
        self.assertEqual("subnet.create", samples[3].name)

    def test_port_create(self):
        v = notifications.Port()
        samples = list(v.process_notification(NOTIFICATION_PORT_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("port.create", samples[1].name)

    def test_bulk_port_create(self):
        v = notifications.Port()
        samples = list(v.process_notification(NOTIFICATION_BULK_PORT_CREATE))
        self.assertEqual(4, len(samples))
        self.assertEqual("port", samples[0].name)
        self.assertEqual("port.create", samples[1].name)
        self.assertEqual("port", samples[2].name)
        self.assertEqual("port.create", samples[3].name)

    def test_port_update(self):
        v = notifications.Port()
        samples = list(v.process_notification(NOTIFICATION_PORT_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("port.update", samples[1].name)

    def test_network_exists(self):
        v = notifications.Network()
        samples = v.process_notification(NOTIFICATION_NETWORK_EXISTS)
        self.assertEqual(1, len(list(samples)))

    def test_router_exists(self):
        v = notifications.Router()
        samples = v.process_notification(NOTIFICATION_ROUTER_EXISTS)
        self.assertEqual(1, len(list(samples)))

    def test_floatingip_exists(self):
        v = notifications.FloatingIP()
        samples = list(v.process_notification(NOTIFICATION_FLOATINGIP_EXISTS))
        self.assertEqual(1, len(samples))
        self.assertEqual("ip.floating", samples[0].name)

    def test_floatingip_update(self):
        v = notifications.FloatingIP()
        samples = list(v.process_notification(NOTIFICATION_FLOATINGIP_UPDATE))
        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[0].name, "ip.floating")

    def test_metering_report(self):
        v = notifications.Bandwidth()
        samples = list(v.process_notification(NOTIFICATION_L3_METER))
        self.assertEqual(1, len(samples))
        self.assertEqual("bandwidth", samples[0].name)


class TestEventTypes(test.BaseTestCase):

    def test_network(self):
        v = notifications.Network()
        events = v.event_types
        assert events

    def test_subnet(self):
        v = notifications.Subnet()
        events = v.event_types
        assert events

    def test_port(self):
        v = notifications.Port()
        events = v.event_types
        assert events

    def test_router(self):
        self.assertTrue(notifications.Router().event_types)

    def test_floatingip(self):
        self.assertTrue(notifications.FloatingIP().event_types)

    def test_bandwidth(self):
        self.assertTrue(notifications.Bandwidth().event_types)
