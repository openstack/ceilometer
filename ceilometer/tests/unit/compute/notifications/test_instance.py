#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 eNovance
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
"""Tests for converters for producing compute counter messages from
notification events.
"""
from oslotest import base

from ceilometer.compute.notifications import instance
from ceilometer import sample


INSTANCE_CREATE_END = {
    u'_context_auth_token': u'3d8b13de1b7d499587dfc69b77dc09c2',
    u'_context_is_admin': True,
    u'_context_project_id': u'7c150a59fe714e6f9263774af9688f0e',
    u'_context_quota_class': None,
    u'_context_read_deleted': u'no',
    u'_context_remote_address': u'10.0.2.15',
    u'_context_request_id': u'req-d68b36e0-9233-467f-9afb-d81435d64d66',
    u'_context_roles': [u'admin'],
    u'_context_timestamp': u'2012-05-08T20:23:41.425105',
    u'_context_user_id': u'1e3ce043029547f1a61c1996d1a531a2',
    u'event_type': u'compute.instance.create.end',
    u'message_id': u'dae6f69c-00e0-41c0-b371-41ec3b7f4451',
    u'payload': {u'created_at': u'2012-05-08 20:23:41',
                 u'deleted_at': u'',
                 u'disk_gb': 0,
                 u'display_name': u'testme',
                 u'fixed_ips': [{u'address': u'10.0.0.2',
                                 u'floating_ips': [],
                                 u'meta': {},
                                 u'type': u'fixed',
                                 u'version': 4}],
                 u'image_ref_url': u'http://10.0.2.15:9292/images/UUID',
                 u'instance_id': u'9f9d01b9-4a58-4271-9e27-398b21ab20d1',
                 u'instance_type': u'm1.tiny',
                 u'instance_type_id': 2,
                 u'launched_at': u'2012-05-08 20:23:47.985999',
                 u'memory_mb': 512,
                 u'state': u'active',
                 u'state_description': u'',
                 u'tenant_id': u'7c150a59fe714e6f9263774af9688f0e',
                 u'user_id': u'1e3ce043029547f1a61c1996d1a531a2',
                 u'reservation_id': u'1e3ce043029547f1a61c1996d1a531a3',
                 u'vcpus': 1,
                 u'root_gb': 0,
                 u'ephemeral_gb': 0,
                 u'host': u'compute-host-name',
                 u'availability_zone': u'1e3ce043029547f1a61c1996d1a531a4',
                 u'os_type': u'linux?',
                 u'architecture': u'x86',
                 u'image_ref': u'UUID',
                 u'kernel_id': u'1e3ce043029547f1a61c1996d1a531a5',
                 u'ramdisk_id': u'1e3ce043029547f1a61c1996d1a531a6',
                 },
    u'priority': u'INFO',
    u'publisher_id': u'compute.vagrant-precise',
    u'timestamp': u'2012-05-08 20:23:48.028195',
}

INSTANCE_DELETE_START = {
    u'_context_auth_token': u'3d8b13de1b7d499587dfc69b77dc09c2',
    u'_context_is_admin': True,
    u'_context_project_id': u'7c150a59fe714e6f9263774af9688f0e',
    u'_context_quota_class': None,
    u'_context_read_deleted': u'no',
    u'_context_remote_address': u'10.0.2.15',
    u'_context_request_id': u'req-fb3c4546-a2e5-49b7-9fd2-a63bd658bc39',
    u'_context_roles': [u'admin'],
    u'_context_timestamp': u'2012-05-08T20:24:14.547374',
    u'_context_user_id': u'1e3ce043029547f1a61c1996d1a531a2',
    u'event_type': u'compute.instance.delete.start',
    u'message_id': u'a15b94ee-cb8e-4c71-9abe-14aa80055fb4',
    u'payload': {u'created_at': u'2012-05-08 20:23:41',
                 u'deleted_at': u'',
                 u'disk_gb': 0,
                 u'display_name': u'testme',
                 u'image_ref_url': u'http://10.0.2.15:9292/images/UUID',
                 u'instance_id': u'9f9d01b9-4a58-4271-9e27-398b21ab20d1',
                 u'instance_type': u'm1.tiny',
                 u'instance_type_id': 2,
                 u'launched_at': u'2012-05-08 20:23:47',
                 u'memory_mb': 512,
                 u'state': u'active',
                 u'state_description': u'deleting',
                 u'tenant_id': u'7c150a59fe714e6f9263774af9688f0e',
                 u'user_id': u'1e3ce043029547f1a61c1996d1a531a2',
                 u'reservation_id': u'1e3ce043029547f1a61c1996d1a531a3',
                 u'vcpus': 1,
                 u'root_gb': 0,
                 u'ephemeral_gb': 0,
                 u'host': u'compute-host-name',
                 u'availability_zone': u'1e3ce043029547f1a61c1996d1a531a4',
                 u'os_type': u'linux?',
                 u'architecture': u'x86',
                 u'image_ref': u'UUID',
                 u'kernel_id': u'1e3ce043029547f1a61c1996d1a531a5',
                 u'ramdisk_id': u'1e3ce043029547f1a61c1996d1a531a6',
                 },
    u'priority': u'INFO',
    u'publisher_id': u'compute.vagrant-precise',
    u'timestamp': u'2012-05-08 20:24:14.824743',
}

INSTANCE_EXISTS = {
    u'_context_auth_token': None,
    u'_context_is_admin': True,
    u'_context_project_id': None,
    u'_context_quota_class': None,
    u'_context_read_deleted': u'no',
    u'_context_remote_address': None,
    u'_context_request_id': u'req-659a8eb2-4372-4c01-9028-ad6e40b0ed22',
    u'_context_roles': [u'admin'],
    u'_context_timestamp': u'2012-05-08T16:03:43.760204',
    u'_context_user_id': None,
    u'event_type': u'compute.instance.exists',
    u'message_id': u'4b884c03-756d-4c06-8b42-80b6def9d302',
    u'payload': {u'audit_period_beginning': u'2012-05-08 15:00:00',
                 u'audit_period_ending': u'2012-05-08 16:00:00',
                 u'bandwidth': {},
                 u'created_at': u'2012-05-07 22:16:18',
                 u'deleted_at': u'',
                 u'disk_gb': 0,
                 u'display_name': u'testme',
                 u'image_ref_url': u'http://10.0.2.15:9292/images/UUID',
                 u'instance_id': u'3a513875-95c9-4012-a3e7-f90c678854e5',
                 u'instance_type': u'm1.tiny',
                 u'instance_type_id': 2,
                 u'launched_at': u'2012-05-07 23:01:27',
                 u'memory_mb': 512,
                 u'state': u'active',
                 u'state_description': u'',
                 u'tenant_id': u'7c150a59fe714e6f9263774af9688f0e',
                 u'user_id': u'1e3ce043029547f1a61c1996d1a531a2',
                 u'reservation_id': u'1e3ce043029547f1a61c1996d1a531a3',
                 u'vcpus': 1,
                 u'root_gb': 0,
                 u'ephemeral_gb': 0,
                 u'host': u'compute-host-name',
                 u'availability_zone': u'1e3ce043029547f1a61c1996d1a531a4',
                 u'os_type': u'linux?',
                 u'architecture': u'x86',
                 u'image_ref': u'UUID',
                 u'kernel_id': u'1e3ce043029547f1a61c1996d1a531a5',
                 u'ramdisk_id': u'1e3ce043029547f1a61c1996d1a531a6',
                 },
    u'priority': u'INFO',
    u'publisher_id': u'compute.vagrant-precise',
    u'timestamp': u'2012-05-08 16:03:44.122481',
}

INSTANCE_EXISTS_METADATA_LIST = {
    u'_context_auth_token': None,
    u'_context_is_admin': True,
    u'_context_project_id': None,
    u'_context_quota_class': None,
    u'_context_read_deleted': u'no',
    u'_context_remote_address': None,
    u'_context_request_id': u'req-659a8eb2-4372-4c01-9028-ad6e40b0ed22',
    u'_context_roles': [u'admin'],
    u'_context_timestamp': u'2012-05-08T16:03:43.760204',
    u'_context_user_id': None,
    u'event_type': u'compute.instance.exists',
    u'message_id': u'4b884c03-756d-4c06-8b42-80b6def9d302',
    u'payload': {u'audit_period_beginning': u'2012-05-08 15:00:00',
                 u'audit_period_ending': u'2012-05-08 16:00:00',
                 u'bandwidth': {},
                 u'created_at': u'2012-05-07 22:16:18',
                 u'deleted_at': u'',
                 u'disk_gb': 0,
                 u'display_name': u'testme',
                 u'image_ref_url': u'http://10.0.2.15:9292/images/UUID',
                 u'instance_id': u'3a513875-95c9-4012-a3e7-f90c678854e5',
                 u'instance_type': u'm1.tiny',
                 u'instance_type_id': 2,
                 u'launched_at': u'2012-05-07 23:01:27',
                 u'memory_mb': 512,
                 u'state': u'active',
                 u'state_description': u'',
                 u'tenant_id': u'7c150a59fe714e6f9263774af9688f0e',
                 u'user_id': u'1e3ce043029547f1a61c1996d1a531a2',
                 u'reservation_id': u'1e3ce043029547f1a61c1996d1a531a3',
                 u'vcpus': 1,
                 u'root_gb': 0,
                 u'metadata': [],
                 u'ephemeral_gb': 0,
                 u'host': u'compute-host-name',
                 u'availability_zone': u'1e3ce043029547f1a61c1996d1a531a4',
                 u'os_type': u'linux?',
                 u'architecture': u'x86',
                 u'image_ref': u'UUID',
                 u'kernel_id': u'1e3ce043029547f1a61c1996d1a531a5',
                 u'ramdisk_id': u'1e3ce043029547f1a61c1996d1a531a6',
                 },
    u'priority': u'INFO',
    u'publisher_id': u'compute.vagrant-precise',
    u'timestamp': u'2012-05-08 16:03:44.122481',
}


INSTANCE_FINISH_RESIZE_END = {
    u'_context_roles': [u'admin'],
    u'_context_request_id': u'req-e3f71bb9-e9b9-418b-a9db-a5950c851b25',
    u'_context_quota_class': None,
    u'event_type': u'compute.instance.finish_resize.end',
    u'_context_user_name': u'admin',
    u'_context_project_name': u'admin',
    u'timestamp': u'2013-01-04 15:10:17.436974',
    u'_context_is_admin': True,
    u'message_id': u'a2f7770d-b85d-4797-ab10-41407a44368e',
    u'_context_auth_token': None,
    u'_context_instance_lock_checked': False,
    u'_context_project_id': u'cea4b25edb484e5392727181b7721d29',
    u'_context_timestamp': u'2013-01-04T15:08:39.162612',
    u'_context_read_deleted': u'no',
    u'_context_user_id': u'01b83a5e23f24a6fb6cd073c0aee6eed',
    u'_context_remote_address': u'10.147.132.184',
    u'publisher_id': u'compute.ip-10-147-132-184.ec2.internal',
    u'payload': {u'state_description': u'',
                 u'availability_zone': None,
                 u'ephemeral_gb': 0,
                 u'instance_type_id': 5,
                 u'deleted_at': u'',
                 u'fixed_ips': [{u'floating_ips': [],
                                 u'label': u'private',
                                 u'version': 4,
                                 u'meta': {},
                                 u'address': u'10.0.0.3',
                                 u'type': u'fixed'}],
                 u'memory_mb': 2048,
                 u'user_id': u'01b83a5e23f24a6fb6cd073c0aee6eed',
                 u'reservation_id': u'r-u3fvim06',
                 u'hostname': u's1',
                 u'state': u'resized',
                 u'launched_at': u'2013-01-04T15:10:14.923939',
                 u'metadata': {u'metering.server_group': u'Group_A',
                               u'AutoScalingGroupName': u'tyky-Group_Awste7',
                               u'metering.foo.bar': u'true'},
                 u'ramdisk_id': u'5f23128e-5525-46d8-bc66-9c30cd87141a',
                 u'access_ip_v6': None,
                 u'disk_gb': 20,
                 u'access_ip_v4': None,
                 u'kernel_id': u'571478e0-d5e7-4c2e-95a5-2bc79443c28a',
                 u'host': u'ip-10-147-132-184.ec2.internal',
                 u'display_name': u's1',
                 u'image_ref_url': u'http://10.147.132.184:9292/images/'
                 'a130b9d9-e00e-436e-9782-836ccef06e8a',
                 u'root_gb': 20,
                 u'tenant_id': u'cea4b25edb484e5392727181b7721d29',
                 u'created_at': u'2013-01-04T11:21:48.000000',
                 u'instance_id': u'648e8963-6886-4c3c-98f9-4511c292f86b',
                 u'instance_type': u'm1.small',
                 u'vcpus': 1,
                 u'image_meta': {u'kernel_id':
                                 u'571478e0-d5e7-4c2e-95a5-2bc79443c28a',
                                 u'ramdisk_id':
                                 u'5f23128e-5525-46d8-bc66-9c30cd87141a',
                                 u'base_image_ref':
                                 u'a130b9d9-e00e-436e-9782-836ccef06e8a'},
                 u'architecture': None,
                 u'os_type': None
                 },
    u'priority': u'INFO'
}

INSTANCE_RESIZE_REVERT_END = {
    u'_context_roles': [u'admin'],
    u'_context_request_id': u'req-9da1d714-dabe-42fd-8baa-583e57cd4f1a',
    u'_context_quota_class': None,
    u'event_type': u'compute.instance.resize.revert.end',
    u'_context_user_name': u'admin',
    u'_context_project_name': u'admin',
    u'timestamp': u'2013-01-04 15:20:32.009532',
    u'_context_is_admin': True,
    u'message_id': u'c48deeba-d0c3-4154-b3db-47480b52267a',
    u'_context_auth_token': None,
    u'_context_instance_lock_checked': False,
    u'_context_project_id': u'cea4b25edb484e5392727181b7721d29',
    u'_context_timestamp': u'2013-01-04T15:19:51.018218',
    u'_context_read_deleted': u'no',
    u'_context_user_id': u'01b83a5e23f24a6fb6cd073c0aee6eed',
    u'_context_remote_address': u'10.147.132.184',
    u'publisher_id': u'compute.ip-10-147-132-184.ec2.internal',
    u'payload': {u'state_description': u'resize_reverting',
                 u'availability_zone': None,
                 u'ephemeral_gb': 0,
                 u'instance_type_id': 2,
                 u'deleted_at': u'',
                 u'reservation_id': u'r-u3fvim06',
                 u'memory_mb': 512,
                 u'user_id': u'01b83a5e23f24a6fb6cd073c0aee6eed',
                 u'hostname': u's1',
                 u'state': u'resized',
                 u'launched_at': u'2013-01-04T15:10:14.000000',
                 u'metadata': {u'metering.server_group': u'Group_A',
                               u'AutoScalingGroupName': u'tyky-Group_A-wste7',
                               u'metering.foo.bar': u'true'},
                 u'ramdisk_id': u'5f23128e-5525-46d8-bc66-9c30cd87141a',
                 u'access_ip_v6': None,
                 u'disk_gb': 0,
                 u'access_ip_v4': None,
                 u'kernel_id': u'571478e0-d5e7-4c2e-95a5-2bc79443c28a',
                 u'host': u'ip-10-147-132-184.ec2.internal',
                 u'display_name': u's1',
                 u'image_ref_url': u'http://10.147.132.184:9292/images/'
                 'a130b9d9-e00e-436e-9782-836ccef06e8a',
                 u'root_gb': 0,
                 u'tenant_id': u'cea4b25edb484e5392727181b7721d29',
                 u'created_at': u'2013-01-04T11:21:48.000000',
                 u'instance_id': u'648e8963-6886-4c3c-98f9-4511c292f86b',
                 u'instance_type': u'm1.tiny',
                 u'vcpus': 1,
                 u'image_meta': {u'kernel_id':
                                 u'571478e0-d5e7-4c2e-95a5-2bc79443c28a',
                                 u'ramdisk_id':
                                 u'5f23128e-5525-46d8-bc66-9c30cd87141a',
                                 u'base_image_ref':
                                 u'a130b9d9-e00e-436e-9782-836ccef06e8a'},
                 u'architecture': None,
                 u'os_type': None
                 },
    u'priority': u'INFO'
}

INSTANCE_SCHEDULED = {
    u'_context_request_id': u'req-f28a836a-32bf-4cc3-940a-3515878c181f',
    u'_context_quota_class': None,
    u'event_type': u'scheduler.run_instance.scheduled',
    u'_context_service_catalog': [{
        u'endpoints': [{
            u'adminURL':
            u'http://172.16.12.21:8776/v1/2bd766a095b44486bf07cf7f666997eb',
            u'region': u'RegionOne',
            u'internalURL':
            u'http://172.16.12.21:8776/v1/2bd766a095b44486bf07cf7f666997eb',
            u'id': u'30cb904fdc294eea9b225e06b2d0d4eb',
            u'publicURL':
            u'http://172.16.12.21:8776/v1/2bd766a095b44486bf07cf7f666997eb'}],
        u'endpoints_links': [],
        u'type': u'volume',
        u'name': u'cinder'}],
    u'_context_auth_token': u'TOK',
    u'_context_user_id': u'0a757cd896b64b65ba3784afef564116',
    u'payload': {
        'instance_id': 'fake-uuid1-1',
        u'weighted_host': {u'host': u'eglynn-f19-devstack3', u'weight': 1.0},
        u'request_spec': {
            u'num_instances': 1,
            u'block_device_mapping': [{
                u'instance_uuid': u'9206baae-c3b6-41bc-96f2-2c0726ff51c8',
                u'guest_format': None,
                u'boot_index': 0,
                u'no_device': None,
                u'connection_info': None,
                u'volume_id': None,
                u'volume_size': None,
                u'device_name': None,
                u'disk_bus': None,
                u'image_id': u'0560ac3f-3bcd-434d-b012-8dd7a212b73b',
                u'source_type': u'image',
                u'device_type': u'disk',
                u'snapshot_id': None,
                u'destination_type': u'local',
                u'delete_on_termination': True}],
            u'image': {
                u'status': u'active',
                u'name': u'cirros-0.3.1-x86_64-uec',
                u'deleted': False,
                u'container_format': u'ami',
                u'created_at': u'2014-02-18T13:16:26.000000',
                u'disk_format': u'ami',
                u'updated_at': u'2014-02-18T13:16:27.000000',
                u'properties': {
                    u'kernel_id': u'c8794c1a-4158-42cc-9f97-d0d250c9c6a4',
                    u'ramdisk_id': u'4999726c-545c-4a9e-bfc0-917459784275'},
                u'min_disk': 0,
                u'min_ram': 0,
                u'checksum': u'f8a2eeee2dc65b3d9b6e63678955bd83',
                u'owner': u'2bd766a095b44486bf07cf7f666997eb',
                u'is_public': True,
                u'deleted_at': None,
                u'id': u'0560ac3f-3bcd-434d-b012-8dd7a212b73b',
                u'size': 25165824},
            u'instance_type': {
                u'root_gb': 1,
                u'name': u'm1.tiny',
                u'ephemeral_gb': 0,
                u'memory_mb': 512,
                u'vcpus': 1,
                u'extra_specs': {},
                u'swap': 0,
                u'rxtx_factor': 1.0,
                u'flavorid': u'1',
                u'vcpu_weight': None,
                u'id': 2},
            u'instance_properties': {
                u'vm_state': u'building',
                u'availability_zone': None,
                u'terminated_at': None,
                u'ephemeral_gb': 0,
                u'instance_type_id': 2,
                u'user_data': None,
                u'cleaned': False,
                u'vm_mode': None,
                u'deleted_at': None,
                u'reservation_id': u'r-ven5q6om',
                u'id': 15,
                u'security_groups': [{
                    u'deleted_at': None,
                    u'user_id': u'0a757cd896b64b65ba3784afef564116',
                    u'description': u'default',
                    u'deleted': False,
                    u'created_at': u'2014-02-19T11:02:31.000000',
                    u'updated_at': None,
                    u'project_id': u'2bd766a095b44486bf07cf7f666997eb',
                    u'id': 1,
                    u'name': u'default'}],
                u'disable_terminate': False,
                u'root_device_name': None,
                u'display_name': u'new',
                u'uuid': u'9206baae-c3b6-41bc-96f2-2c0726ff51c8',
                u'default_swap_device': None,
                u'info_cache': {
                    u'instance_uuid': u'9206baae-c3b6-41bc-96f2-2c0726ff51c8',
                    u'deleted': False,
                    u'created_at': u'2014-03-05T12:44:00.000000',
                    u'updated_at': None,
                    u'network_info': [],
                    u'deleted_at': None},
                u'hostname': u'new',
                u'launched_on': None,
                u'display_description': u'new',
                u'key_data': None,
                u'deleted': False,
                u'config_drive': u'',
                u'power_state': 0,
                u'default_ephemeral_device': None,
                u'progress': 0,
                u'project_id': u'2bd766a095b44486bf07cf7f666997eb',
                u'launched_at': None,
                u'scheduled_at': None,
                u'node': None,
                u'ramdisk_id': u'4999726c-545c-4a9e-bfc0-917459784275',
                u'access_ip_v6': None,
                u'access_ip_v4': None,
                u'kernel_id': u'c8794c1a-4158-42cc-9f97-d0d250c9c6a4',
                u'key_name': None,
                u'updated_at': None,
                u'host': None,
                u'root_gb': 1,
                u'user_id': u'0a757cd896b64b65ba3784afef564116',
                u'system_metadata': {
                    u'image_kernel_id':
                    u'c8794c1a-4158-42cc-9f97-d0d250c9c6a4',
                    u'image_min_disk': u'1',
                    u'instance_type_memory_mb': u'512',
                    u'instance_type_swap': u'0',
                    u'instance_type_vcpu_weight': None,
                    u'instance_type_root_gb': u'1',
                    u'instance_type_name': u'm1.tiny',
                    u'image_ramdisk_id':
                    u'4999726c-545c-4a9e-bfc0-917459784275',
                    u'instance_type_id': u'2',
                    u'instance_type_ephemeral_gb': u'0',
                    u'instance_type_rxtx_factor': u'1.0',
                    u'instance_type_flavorid': u'1',
                    u'instance_type_vcpus': u'1',
                    u'image_container_format': u'ami',
                    u'image_min_ram': u'0',
                    u'image_disk_format': u'ami',
                    u'image_base_image_ref':
                    u'0560ac3f-3bcd-434d-b012-8dd7a212b73b'},
                u'task_state': u'scheduling',
                u'shutdown_terminate': False,
                u'cell_name': None,
                u'ephemeral_key_uuid': None,
                u'locked': False,
                u'name': u'instance-0000000f',
                u'created_at': u'2014-03-05T12:44:00.000000',
                u'locked_by': None,
                u'launch_index': 0,
                u'memory_mb': 512,
                u'vcpus': 1,
                u'image_ref': u'0560ac3f-3bcd-434d-b012-8dd7a212b73b',
                u'architecture': None,
                u'auto_disk_config': False,
                u'os_type': None,
                u'metadata': {u'metering.server_group': u'Group_A',
                              u'AutoScalingGroupName': u'tyky-Group_Awste7',
                              u'metering.foo.bar': u'true'}},
                u'security_group': [u'default'],
                u'instance_uuids': [u'9206baae-c3b6-41bc-96f2-2c0726ff51c8']}},
    u'priority': u'INFO',
    u'_context_is_admin': True,
    u'_context_timestamp': u'2014-03-05T12:44:00.135674',
    u'publisher_id': u'scheduler.eglynn-f19-devstack3',
    u'message_id': u'd6c1ae63-a26b-47c7-8397-8794216e09dd',
    u'_context_remote_address': u'172.16.12.21',
    u'_context_roles': [u'_member_', u'admin'],
    u'timestamp': u'2014-03-05 12:44:00.733758',
    u'_context_user': u'0a757cd896b64b65ba3784afef564116',
    u'_unique_id': u'2af47cbdde604ff794bb046f3f9db1e2',
    u'_context_project_name': u'admin',
    u'_context_read_deleted': u'no',
    u'_context_tenant': u'2bd766a095b44486bf07cf7f666997eb',
    u'_context_instance_lock_checked': False,
    u'_context_project_id': u'2bd766a095b44486bf07cf7f666997eb',
    u'_context_user_name': u'admin'
}


class TestNotifications(base.BaseTestCase):

    def test_process_notification(self):
        info = list(instance.Instance(None).process_notification(
            INSTANCE_CREATE_END
        ))[0]
        for name, actual, expected in [
                ('counter_name', info.name, 'instance'),
                ('counter_type', info.type, sample.TYPE_GAUGE),
                ('counter_volume', info.volume, 1),
                ('timestamp', info.timestamp,
                 INSTANCE_CREATE_END['timestamp']),
                ('resource_id', info.resource_id,
                 INSTANCE_CREATE_END['payload']['instance_id']),
                ('instance_type_id',
                 info.resource_metadata['instance_type_id'],
                 INSTANCE_CREATE_END['payload']['instance_type_id']),
                ('host', info.resource_metadata['host'],
                 INSTANCE_CREATE_END['publisher_id']),
        ]:
            self.assertEqual(expected, actual, name)

    @staticmethod
    def _find_counter(counters, name):
        return filter(lambda counter: counter.name == name, counters)[0]

    def _verify_user_metadata(self, metadata):
        self.assertIn('user_metadata', metadata)
        user_meta = metadata['user_metadata']
        self.assertEqual('Group_A', user_meta.get('server_group'))
        self.assertNotIn('AutoScalingGroupName', user_meta)
        self.assertIn('foo_bar', user_meta)
        self.assertNotIn('foo.bar', user_meta)

    def test_instance_create_instance(self):
        ic = instance.Instance(None)
        counters = list(ic.process_notification(INSTANCE_CREATE_END))
        self.assertEqual(1, len(counters))
        c = counters[0]
        self.assertEqual(1, c.volume)

    def test_instance_exists_instance(self):
        ic = instance.Instance(None)
        counters = list(ic.process_notification(INSTANCE_EXISTS))
        self.assertEqual(1, len(counters))

    def test_instance_exists_metadata_list(self):
        ic = instance.Instance(None)
        counters = list(ic.process_notification(INSTANCE_EXISTS_METADATA_LIST))
        self.assertEqual(1, len(counters))

    def test_instance_delete_instance(self):
        ic = instance.Instance(None)
        counters = list(ic.process_notification(INSTANCE_DELETE_START))
        self.assertEqual(1, len(counters))

    def test_instance_finish_resize_instance(self):
        ic = instance.Instance(None)
        counters = list(ic.process_notification(INSTANCE_FINISH_RESIZE_END))
        self.assertEqual(1, len(counters))
        c = counters[0]
        self.assertEqual(1, c.volume)
        self._verify_user_metadata(c.resource_metadata)

    def test_instance_resize_finish_instance(self):
        ic = instance.Instance(None)
        counters = list(ic.process_notification(INSTANCE_FINISH_RESIZE_END))
        self.assertEqual(1, len(counters))
        c = counters[0]
        self.assertEqual(1, c.volume)
        self._verify_user_metadata(c.resource_metadata)

    def test_instance_scheduled(self):
        ic = instance.InstanceScheduled(None)

        self.assertIn(INSTANCE_SCHEDULED['event_type'],
                      ic.event_types)

        counters = list(ic.process_notification(INSTANCE_SCHEDULED))
        self.assertEqual(1, len(counters))
        names = [c.name for c in counters]
        self.assertEqual(['instance.scheduled'], names)
        rid = [c.resource_id for c in counters]
        self.assertEqual(['fake-uuid1-1'], rid)
