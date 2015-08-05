#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

import mock

from ceilometer.network import notifications
from ceilometer.tests import base as test

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


NOTIFICATION_FLOATINGIP_UPDATE_START = {
    '_context_roles': [u'_member_',
                       u'admin',
                       u'heat_stack_owner'],
    '_context_request_id': u'req-bd5ed336-242f-4705-836e-8e8f3d0d1ced',
    '_context_read_deleted': u'no',
    'event_type': u'floatingip.update.start',
    '_context_user_name': u'admin',
    '_context_project_name': u'admin',
    'timestamp': u'2014-05-3107: 19: 43.463101',
    '_context_tenant_id': u'9fc714821a3747c8bc4e3a9bfbe82732',
    '_context_tenant_name': u'admin',
    '_context_tenant': u'9fc714821a3747c8bc4e3a9bfbe82732',
    'message_id': u'0ab6d71f-ba0a-4501-86fe-6cc20521ef5a',
    'priority': 'info',
    '_context_is_admin': True,
    '_context_project_id': u'9fc714821a3747c8bc4e3a9bfbe82732',
    '_context_timestamp': u'2014-05-3107: 19: 43.460767',
    '_context_user': u'6ca7b13b33e4425cae0b85e2cf93d9a1',
    '_context_user_id': u'6ca7b13b33e4425cae0b85e2cf93d9a1',
    'publisher_id': u'network.devstack',
    'payload': {
        u'id': u'64262b2a-8f5d-4ade-9405-0cbdd03c1555',
        u'floatingip': {
            u'fixed_ip_address': u'172.24.4.227',
            u'port_id': u'8ab815c8-03cc-4b45-a673-79bdd0c258f2'
        }
    }
}


NOTIFICATION_POOL_CREATE = {
    "_context_roles": ["heat_stack_owner", "admin"],
    "_context_request_id": "req-10715057-7590-4529-8020-b994295ee6f4",
    "event_type": "pool.create.end",
    "timestamp": "2014-09-15 17:20:50.687649",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "ce255443233748ce9cc71b480974df28",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "pool": {
            "status": "ACTIVE",
            "lb_method": "ROUND_ROBIN",
            "protocol": "HTTP", "description": "",
            "health_monitors": [],
            "members": [],
            "status_description": None,
            "id": "6d726518-f3aa-4dd4-ac34-e156a35c0aff",
            "vip_id": None,
            "name": "my_pool",
            "admin_state_up": True,
            "subnet_id": "afaf251b-2ec3-42ac-9fa9-82a4195724fa",
            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
            "health_monitors_status": [],
            "provider": "haproxy"}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:20:49.600299",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "0a5ed7a6-e516-4aed-9968-4ee9f1b65cc2"}


NOTIFICATION_VIP_CREATE = {
    "_context_roles": ["heat_stack_owner", "admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "vip.create.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "vip": {
            "status": "ACTIVE",
            "protocol": "HTTP",
            "description": "",
            "address": "10.0.0.2",
            "protocol_port": 80,
            "port_id": "2b5dd476-11da-4d46-9f1e-7a75436062f6",
            "id": "87a5ce35-f278-47f3-8990-7f695f52f9bf",
            "status_description": None,
            "name": "my_vip",
            "admin_state_up": True,
            "subnet_id": "afaf251b-2ec3-42ac-9fa9-82a4195724fa",
            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
            "connection_limit": -1,
            "pool_id": "6d726518-f3aa-4dd4-ac34-e156a35c0aff",
            "session_persistence": {"type": "SOURCE_IP"}}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "3895ad11-98a3-4031-92af-f76e96736661"}


NOTIFICATION_HEALTH_MONITORS_CREATE = {
    "_context_roles": ["heat_stack_owner", "admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "health_monitor.create.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "health_monitor": {
            "admin_state_up": True,
            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
            "delay": 10,
            "max_retries": 10,
            "timeout": 10,
            "pools": [],
            "type": "PING",
            "id": "6dea2d01-c3af-4696-9192-6c938f391f01"}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "65067e3f-830d-4fbb-87e2-f0e51fda83d2"}


NOTIFICATION_MEMBERS_CREATE = {
    "_context_roles": ["heat_stack_owner", "admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "member.create.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "member": {"admin_state_up": True,
                   "status": "ACTIVE",
                   "status_description": None,
                   "weight": 1,
                   "address": "10.0.0.3",
                   "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
                   "protocol_port": 80,
                   "id": "5e32f960-63ae-4a93-bfa2-339aa83d82ce",
                   "pool_id": "6b73b9f8-d807-4553-87df-eb34cdd08070"}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "65067e3f-830d-4fbb-87e2-f0e51fda83d2"}


NOTIFICATION_FIREWALL_CREATE = {
    "_context_roles": ["heat_stack_owner", "admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "firewall.create.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "firewall": {
            "status": "ACTIVE",
            "name": "my_firewall",
            "admin_state_up": True,
            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
            "firewall_policy_id": "c46a1c15-0496-41c9-beff-9a309a25653e",
            "id": "e2d1155f-6bc4-4292-9cfa-ea91af4b38c8",
            "description": ""}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "fdffeca1-2b5a-4dc9-b8ae-87c482a83e0d"}


NOTIFICATION_FIREWALL_RULE_CREATE = {
    "_context_roles": ["heat_stack_owner", "admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "firewall_rule.create.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "firewall_rule": {
            "protocol": "tcp",
            "description": "",
            "source_port": 80,
            "source_ip_address": '192.168.255.10',
            "destination_ip_address": '10.10.10.1',
            "firewall_policy_id": '',
            "position": None,
            "destination_port": 80,
            "id": "53b7c0d3-cb87-4069-9e29-1e866583cc8c",
            "name": "rule_01",
            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
            "enabled": True,
            "action": "allow",
            "ip_version": 4,
            "shared": False}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "fdffeca1-2b5a-4dc9-b8ae-87c482a83e0d"}


NOTIFICATION_FIREWALL_POLICY_CREATE = {
    "_context_roles": ["heat_stack_owner", "admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "firewall_policy.create.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "firewall_policy": {"name": "my_policy",
                            "firewall_rules": [],
                            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
                            "audited": False,
                            "shared": False,
                            "id": "c46a1c15-0496-41c9-beff-9a309a25653e",
                            "description": ""}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "fdffeca1-2b5a-4dc9-b8ae-87c482a83e0d"}


NOTIFICATION_VPNSERVICE_CREATE = {
    "_context_roles": ["heat_stack_owner", "admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "vpnservice.create.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "vpnservice": {"router_id": "75871c53-e722-4b21-93ed-20cb40b6b672",
                       "status": "ACTIVE",
                       "name": "my_vpn",
                       "admin_state_up": True,
                       "subnet_id": "afaf251b-2ec3-42ac-9fa9-82a4195724fa",
                       "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
                       "id": "270c40cc-28d5-4a7e-83da-cc33088ee5d6",
                       "description": ""}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "65067e3f-830d-4fbb-87e2-f0e51fda83d2"}


NOTIFICATION_IPSEC_POLICY_CREATE = {
    "_context_roles": ["heat_stack_owner", "admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "ipsecpolicy.create.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "ipsecpolicy": {"encapsulation_mode": "tunnel",
                        "encryption_algorithm": "aes-128",
                        "pfs": "group5",
                        "lifetime": {
                            "units": "seconds",
                            "value": 3600},
                        "name": "my_ipsec_polixy",
                        "transform_protocol": "esp",
                        "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
                        "id": "998d910d-4506-47c9-a160-47ec51ff53fc",
                        "auth_algorithm": "sha1",
                        "description": ""}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "4c0e6ecb-2e40-4975-aee2-d88045c747bf"}


NOTIFICATION_IKE_POLICY_CREATE = {
    "_context_roles": ["heat_stack_owner", "admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "ikepolicy.create.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "ikepolicy": {"encryption_algorithm": "aes-128",
                      "pfs": "group5",
                      "name": "my_ike_policy",
                      "phase1_negotiation_mode": "main",
                      "lifetime": {"units": "seconds",
                                   "value": 3600},
                      "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
                      "ike_version": "v1",
                      "id": "11cef94e-3f6a-4b65-8058-7deb1838633a",
                      "auth_algorithm": "sha1",
                      "description": ""}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "4c0e6ecb-2e40-4975-aee2-d88045c747bf"}


NOTIFICATION_IPSEC_SITE_CONN_CREATE = {
    "_context_roles": ["heat_stack_owner", "admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "ipsec_site_connection.create.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "ipsec_site_connection": {
            "status": "ACTIVE",
            "psk": "test",
            "initiator": "bi-directional",
            "name": "my_ipsec_connection",
            "admin_state_up": True,
            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
            "ipsecpolicy_id": "998d910d-4506-47c9-a160-47ec51ff53fc",
            "auth_mode": "psk", "peer_cidrs": ["192.168.255.0/24"],
            "mtu": 1500,
            "ikepolicy_id": "11cef94e-3f6a-4b65-8058-7deb1838633a",
            "dpd": {"action": "hold",
                    "interval": 30,
                    "timeout": 120},
            "route_mode": "static",
            "vpnservice_id": "270c40cc-28d5-4a7e-83da-cc33088ee5d6",
            "peer_address": "10.0.0.1",
            "peer_id": "10.0.0.254",
            "id": "06f3c1ec-2e01-4ad6-9c98-4252751fc60a",
            "description": ""}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "4c0e6ecb-2e40-4975-aee2-d88045c747bf"}


NOTIFICATION_POOL_UPDATE = {
    "_context_roles": ["admin"],
    "_context_request_id": "req-10715057-7590-4529-8020-b994295ee6f4",
    "event_type": "pool.update.end",
    "timestamp": "2014-09-15 17:20:50.687649",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "ce255443233748ce9cc71b480974df28",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "pool": {
            "status": "ACTIVE",
            "lb_method": "ROUND_ROBIN",
            "protocol": "HTTP", "description": "",
            "health_monitors": [],
            "members": [],
            "status_description": None,
            "id": "6d726518-f3aa-4dd4-ac34-e156a35c0aff",
            "vip_id": None,
            "name": "my_pool",
            "admin_state_up": True,
            "subnet_id": "afaf251b-2ec3-42ac-9fa9-82a4195724fa",
            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
            "health_monitors_status": [],
            "provider": "haproxy"}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:20:49.600299",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "0a5ed7a6-e516-4aed-9968-4ee9f1b65cc2"}


NOTIFICATION_VIP_UPDATE = {
    "_context_roles": ["admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "vip.update.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "vip": {
            "status": "ACTIVE",
            "protocol": "HTTP",
            "description": "",
            "address": "10.0.0.2",
            "protocol_port": 80,
            "port_id": "2b5dd476-11da-4d46-9f1e-7a75436062f6",
            "id": "87a5ce35-f278-47f3-8990-7f695f52f9bf",
            "status_description": None,
            "name": "my_vip",
            "admin_state_up": True,
            "subnet_id": "afaf251b-2ec3-42ac-9fa9-82a4195724fa",
            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
            "connection_limit": -1,
            "pool_id": "6d726518-f3aa-4dd4-ac34-e156a35c0aff",
            "session_persistence": {"type": "SOURCE_IP"}}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "3895ad11-98a3-4031-92af-f76e96736661"}


NOTIFICATION_HEALTH_MONITORS_UPDATE = {
    "_context_roles": ["admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "health_monitor.update.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "health_monitor": {
            "admin_state_up": True,
            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
            "delay": 10,
            "max_retries": 10,
            "timeout": 10,
            "pools": [],
            "type": "PING",
            "id": "6dea2d01-c3af-4696-9192-6c938f391f01"}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "65067e3f-830d-4fbb-87e2-f0e51fda83d2"}


NOTIFICATION_MEMBERS_UPDATE = {
    "_context_roles": ["admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "member.update.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "member": {"admin_state_up": True,
                   "status": "ACTIVE",
                   "status_description": None,
                   "weight": 1,
                   "address": "10.0.0.3",
                   "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
                   "protocol_port": 80,
                   "id": "5e32f960-63ae-4a93-bfa2-339aa83d82ce",
                   "pool_id": "6b73b9f8-d807-4553-87df-eb34cdd08070"}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "65067e3f-830d-4fbb-87e2-f0e51fda83d2"}


NOTIFICATION_FIREWALL_UPDATE = {
    "_context_roles": ["admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "firewall.update.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "firewall": {
            "status": "ACTIVE",
            "name": "my_firewall",
            "admin_state_up": True,
            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
            "firewall_policy_id": "c46a1c15-0496-41c9-beff-9a309a25653e",
            "id": "e2d1155f-6bc4-4292-9cfa-ea91af4b38c8",
            "description": ""}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "fdffeca1-2b5a-4dc9-b8ae-87c482a83e0d"}


NOTIFICATION_FIREWALL_RULE_UPDATE = {
    "_context_roles": ["admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "firewall_rule.update.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "firewall_rule": {
            "protocol": "tcp",
            "description": "",
            "source_port": 80,
            "source_ip_address": '192.168.255.10',
            "destination_ip_address": '10.10.10.1',
            "firewall_policy_id": '',
            "position": None,
            "destination_port": 80,
            "id": "53b7c0d3-cb87-4069-9e29-1e866583cc8c",
            "name": "rule_01",
            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
            "enabled": True,
            "action": "allow",
            "ip_version": 4,
            "shared": False}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "fdffeca1-2b5a-4dc9-b8ae-87c482a83e0d"}


NOTIFICATION_FIREWALL_POLICY_UPDATE = {
    "_context_roles": ["admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "firewall_policy.update.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "firewall_policy": {"name": "my_policy",
                            "firewall_rules": [],
                            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
                            "audited": False,
                            "shared": False,
                            "id": "c46a1c15-0496-41c9-beff-9a309a25653e",
                            "description": ""}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "fdffeca1-2b5a-4dc9-b8ae-87c482a83e0d"}


NOTIFICATION_VPNSERVICE_UPDATE = {
    "_context_roles": ["admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "vpnservice.update.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "vpnservice": {"router_id": "75871c53-e722-4b21-93ed-20cb40b6b672",
                       "status": "ACTIVE",
                       "name": "my_vpn",
                       "admin_state_up": True,
                       "subnet_id": "afaf251b-2ec3-42ac-9fa9-82a4195724fa",
                       "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
                       "id": "270c40cc-28d5-4a7e-83da-cc33088ee5d6",
                       "description": ""}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "65067e3f-830d-4fbb-87e2-f0e51fda83d2"}


NOTIFICATION_IPSEC_POLICY_UPDATE = {
    "_context_roles": ["admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "ipsecpolicy.update.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "ipsecpolicy": {"encapsulation_mode": "tunnel",
                        "encryption_algorithm": "aes-128",
                        "pfs": "group5",
                        "lifetime": {
                            "units": "seconds",
                            "value": 3600},
                        "name": "my_ipsec_polixy",
                        "transform_protocol": "esp",
                        "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
                        "id": "998d910d-4506-47c9-a160-47ec51ff53fc",
                        "auth_algorithm": "sha1",
                        "description": ""}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "4c0e6ecb-2e40-4975-aee2-d88045c747bf"}


NOTIFICATION_IKE_POLICY_UPDATE = {
    "_context_roles": ["admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "ikepolicy.update.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "ikepolicy": {"encryption_algorithm": "aes-128",
                      "pfs": "group5",
                      "name": "my_ike_policy",
                      "phase1_negotiation_mode": "main",
                      "lifetime": {"units": "seconds",
                                   "value": 3600},
                      "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
                      "ike_version": "v1",
                      "id": "11cef94e-3f6a-4b65-8058-7deb1838633a",
                      "auth_algorithm": "sha1",
                      "description": ""}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "4c0e6ecb-2e40-4975-aee2-d88045c747bf"}


NOTIFICATION_IPSEC_SITE_CONN_UPDATE = {
    "_context_roles": ["admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "ipsec_site_connection.update.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "ipsec_site_connection": {
            "status": "ACTIVE",
            "psk": "test",
            "initiator": "bi-directional",
            "name": "my_ipsec_connection",
            "admin_state_up": True,
            "tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
            "ipsecpolicy_id": "998d910d-4506-47c9-a160-47ec51ff53fc",
            "auth_mode": "psk", "peer_cidrs": ["192.168.255.0/24"],
            "mtu": 1500,
            "ikepolicy_id": "11cef94e-3f6a-4b65-8058-7deb1838633a",
            "dpd": {"action": "hold",
                    "interval": 30,
                    "timeout": 120},
            "route_mode": "static",
            "vpnservice_id": "270c40cc-28d5-4a7e-83da-cc33088ee5d6",
            "peer_address": "10.0.0.1",
            "peer_id": "10.0.0.254",
            "id": "06f3c1ec-2e01-4ad6-9c98-4252751fc60a",
            "description": ""}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "4c0e6ecb-2e40-4975-aee2-d88045c747bf"}

NOTIFICATION_EMPTY_PAYLOAD = {
    "_context_roles": ["heat_stack_owner", "admin"],
    "_context_request_id": "req-e56a8a5e-5d42-43e8-9677-2d36e6e17d5e",
    "event_type": "health_monitor.create.end",
    "timestamp": "2014-09-15 17:22:11.323644",
    "_context_tenant_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_user": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "_unique_id": "f112a185e1d1424eba3a13df9e0f0277",
    "_context_tenant_name": "demo",
    "_context_user_id": "1c1f7c80efc24a16b835ae1c0802d0a1",
    "payload": {
        "health_monitor": {}},
    "_context_project_name": "demo",
    "_context_read_deleted": "no",
    "_context_auth_token": "e6daf56d7d1787e1fbefff0ecf29703f",
    "_context_tenant": "a820f2d6293b4a7587d1c582767f43fb",
    "priority": "INFO",
    "_context_is_admin": True,
    "_context_project_id": "a820f2d6293b4a7587d1c582767f43fb",
    "_context_timestamp": "2014-09-15 17:22:11.187163",
    "_context_user_name": "admin",
    "publisher_id": "network.ubuntu",
    "message_id": "65067e3f-830d-4fbb-87e2-f0e51fda83d2"}


class TestNotifications(test.BaseTestCase):
    def test_network_create(self):
        v = notifications.Network(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_NETWORK_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.create", samples[1].name)

    def test_bulk_network_create(self):
        v = notifications.Network(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_BULK_NETWORK_CREATE))
        self.assertEqual(4, len(samples))
        self.assertEqual("network", samples[0].name)
        self.assertEqual("network.create", samples[1].name)
        self.assertEqual("network", samples[2].name)
        self.assertEqual("network.create", samples[3].name)

    def test_subnet_create(self):
        v = notifications.Subnet(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_SUBNET_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("subnet.create", samples[1].name)

    def test_bulk_subnet_create(self):
        v = notifications.Subnet(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_BULK_SUBNET_CREATE))
        self.assertEqual(4, len(samples))
        self.assertEqual("subnet", samples[0].name)
        self.assertEqual("subnet.create", samples[1].name)
        self.assertEqual("subnet", samples[2].name)
        self.assertEqual("subnet.create", samples[3].name)

    def test_port_create(self):
        v = notifications.Port(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_PORT_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("port.create", samples[1].name)

    def test_bulk_port_create(self):
        v = notifications.Port(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_BULK_PORT_CREATE))
        self.assertEqual(4, len(samples))
        self.assertEqual("port", samples[0].name)
        self.assertEqual("port.create", samples[1].name)
        self.assertEqual("port", samples[2].name)
        self.assertEqual("port.create", samples[3].name)

    def test_port_update(self):
        v = notifications.Port(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_PORT_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("port.update", samples[1].name)

    def test_network_exists(self):
        v = notifications.Network(mock.Mock())
        samples = v.process_notification(NOTIFICATION_NETWORK_EXISTS)
        self.assertEqual(1, len(list(samples)))

    def test_router_exists(self):
        v = notifications.Router(mock.Mock())
        samples = v.process_notification(NOTIFICATION_ROUTER_EXISTS)
        self.assertEqual(1, len(list(samples)))

    def test_floatingip_exists(self):
        v = notifications.FloatingIP(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_FLOATINGIP_EXISTS))
        self.assertEqual(1, len(samples))
        self.assertEqual("ip.floating", samples[0].name)

    def test_floatingip_update(self):
        v = notifications.FloatingIP(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_FLOATINGIP_UPDATE_START))
        self.assertEqual(len(samples), 2)
        self.assertEqual("ip.floating", samples[0].name)

    def test_pool_create(self):
        v = notifications.Pool(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_POOL_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.lb.pool", samples[0].name)

    def test_vip_create(self):
        v = notifications.Vip(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VIP_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.lb.vip", samples[0].name)

    def test_member_create(self):
        v = notifications.Member(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_MEMBERS_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.lb.member", samples[0].name)

    def test_health_monitor_create(self):
        v = notifications.HealthMonitor(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_HEALTH_MONITORS_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.lb.health_monitor", samples[0].name)

    def test_firewall_create(self):
        v = notifications.Firewall(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_FIREWALL_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.firewall", samples[0].name)

    def test_vpnservice_create(self):
        v = notifications.VPNService(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VPNSERVICE_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.vpn", samples[0].name)

    def test_ipsec_connection_create(self):
        v = notifications.IPSecSiteConnection(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_IPSEC_SITE_CONN_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.vpn.connections", samples[0].name)

    def test_firewall_policy_create(self):
        v = notifications.FirewallPolicy(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_FIREWALL_POLICY_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.firewall.policy", samples[0].name)

    def test_firewall_rule_create(self):
        v = notifications.FirewallRule(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_FIREWALL_RULE_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.firewall.rule", samples[0].name)

    def test_ipsec_policy_create(self):
        v = notifications.IPSecPolicy(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_IPSEC_POLICY_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.vpn.ipsecpolicy", samples[0].name)

    def test_ike_policy_create(self):
        v = notifications.IKEPolicy(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_IKE_POLICY_CREATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.vpn.ikepolicy", samples[0].name)

    def test_pool_update(self):
        v = notifications.Pool(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_POOL_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.lb.pool", samples[0].name)

    def test_vip_update(self):
        v = notifications.Vip(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VIP_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.lb.vip", samples[0].name)

    def test_member_update(self):
        v = notifications.Member(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_MEMBERS_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.lb.member", samples[0].name)

    def test_health_monitor_update(self):
        v = notifications.HealthMonitor(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_HEALTH_MONITORS_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.lb.health_monitor", samples[0].name)

    def test_firewall_update(self):
        v = notifications.Firewall(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_FIREWALL_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.firewall", samples[0].name)

    def test_vpnservice_update(self):
        v = notifications.VPNService(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VPNSERVICE_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.vpn", samples[0].name)

    def test_ipsec_connection_update(self):
        v = notifications.IPSecSiteConnection(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_IPSEC_SITE_CONN_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.vpn.connections", samples[0].name)

    def test_firewall_policy_update(self):
        v = notifications.FirewallPolicy(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_FIREWALL_POLICY_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.firewall.policy", samples[0].name)

    def test_firewall_rule_update(self):
        v = notifications.FirewallRule(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_FIREWALL_RULE_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.firewall.rule", samples[0].name)

    def test_ipsec_policy_update(self):
        v = notifications.IPSecPolicy(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_IPSEC_POLICY_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.vpn.ipsecpolicy", samples[0].name)

    def test_ike_policy_update(self):
        v = notifications.IKEPolicy(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_IKE_POLICY_UPDATE))
        self.assertEqual(2, len(samples))
        self.assertEqual("network.services.vpn.ikepolicy", samples[0].name)

    def test_empty_event_payload(self):
        v = notifications.HealthMonitor(mock.Mock())
        samples = list(v.process_notification(
            NOTIFICATION_EMPTY_PAYLOAD))
        self.assertEqual(0, len(samples))


class TestEventTypes(test.BaseTestCase):

    def test_network(self):
        v = notifications.Network(mock.Mock())
        events = v.event_types
        self.assertIsNotEmpty(events)

    def test_subnet(self):
        v = notifications.Subnet(mock.Mock())
        events = v.event_types
        self.assertIsNotEmpty(events)

    def test_port(self):
        v = notifications.Port(mock.Mock())
        events = v.event_types
        self.assertIsNotEmpty(events)

    def test_router(self):
        self.assertTrue(notifications.Router(mock.Mock()).event_types)

    def test_floatingip(self):
        self.assertTrue(notifications.FloatingIP(mock.Mock()).event_types)

    def test_pool(self):
        self.assertTrue(notifications.Pool(mock.Mock()).event_types)

    def test_vip(self):
        self.assertTrue(notifications.Vip(mock.Mock()).event_types)

    def test_member(self):
        self.assertTrue(notifications.Member(mock.Mock()).event_types)

    def test_health_monitor(self):
        self.assertTrue(notifications.HealthMonitor(mock.Mock()).event_types)

    def test_firewall(self):
        self.assertTrue(notifications.Firewall(mock.Mock()).event_types)

    def test_vpnservice(self):
        self.assertTrue(notifications.VPNService(mock.Mock()).event_types)

    def test_ipsec_connection(self):
        self.assertTrue(notifications.IPSecSiteConnection(
            mock.Mock()).event_types)

    def test_firewall_policy(self):
        self.assertTrue(notifications.FirewallPolicy(mock.Mock()).event_types)

    def test_firewall_rule(self):
        self.assertTrue(notifications.FirewallRule(mock.Mock()).event_types)

    def test_ipsec_policy(self):
        self.assertTrue(notifications.IPSecPolicy(mock.Mock()).event_types)

    def test_ike_policy(self):
        self.assertTrue(notifications.IKEPolicy(mock.Mock()).event_types)
