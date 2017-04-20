#
# Copyright 2012 eNovance <licensing@enovance.com>
# Copyright 2012 Red Hat, Inc
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
"""Tests for the compute pollsters.
"""

import mock
from oslotest import base
import six

from ceilometer.agent import manager
from ceilometer.compute.pollsters import util
from ceilometer import service


class FauxInstance(object):

    def __init__(self, **kwds):
        for name, value in kwds.items():
            setattr(self, name, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default):
        try:
            return getattr(self, key)
        except AttributeError:
            return default


class TestLocationMetadata(base.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        self.CONF = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, self.CONF)
        super(TestLocationMetadata, self).setUp()

        # Mimics an instance returned from nova api call
        self.INSTANCE_PROPERTIES = {'name': 'display name',
                                    'id': ('234cbe81-4e09-4f64-9b2a-'
                                           '714f6b9046e3'),
                                    'OS-EXT-SRV-ATTR:instance_name':
                                    'instance-000001',
                                    'OS-EXT-AZ:availability_zone':
                                    'foo-zone',
                                    'reservation_id': 'reservation id',
                                    'architecture': 'x86_64',
                                    'kernel_id': 'kernel id',
                                    'os_type': 'linux',
                                    'ramdisk_id': 'ramdisk id',
                                    'status': 'active',
                                    'ephemeral_gb': 0,
                                    'root_gb': 20,
                                    'disk_gb': 20,
                                    'image': {'id': 1,
                                              'links': [{"rel": "bookmark",
                                                         'href': 2}]},
                                    'hostId': '1234-5678',
                                    'OS-EXT-SRV-ATTR:host': 'host-test',
                                    'flavor': {'name': 'm1.tiny',
                                               'id': 1,
                                               'disk': 20,
                                               'ram': 512,
                                               'vcpus': 2,
                                               'ephemeral': 0},
                                    'metadata': {'metering.autoscale.group':
                                                 'X' * 512,
                                                 'metering.ephemeral_gb': 42}}

        self.instance = FauxInstance(**self.INSTANCE_PROPERTIES)

    def test_metadata(self):
        md = util._get_metadata_from_object(self.CONF, self.instance)
        for prop, value in six.iteritems(self.INSTANCE_PROPERTIES):
            if prop not in ("metadata"):
                # Special cases
                if prop == 'name':
                    prop = 'display_name'
                elif prop == 'hostId':
                    prop = "host"
                elif prop == 'OS-EXT-SRV-ATTR:host':
                    prop = "instance_host"
                elif prop == 'OS-EXT-SRV-ATTR:instance_name':
                    prop = 'name'
                elif prop == "id":
                    prop = "instance_id"
                self.assertEqual(value, md[prop])
        user_metadata = md['user_metadata']
        expected = self.INSTANCE_PROPERTIES[
            'metadata']['metering.autoscale.group'][:256]
        self.assertEqual(expected, user_metadata['autoscale_group'])
        self.assertEqual(1, len(user_metadata))

    def test_metadata_empty_image(self):
        self.INSTANCE_PROPERTIES['image'] = None
        self.instance = FauxInstance(**self.INSTANCE_PROPERTIES)
        md = util._get_metadata_from_object(self.CONF, self.instance)
        self.assertIsNone(md['image'])
        self.assertIsNone(md['image_ref'])
        self.assertIsNone(md['image_ref_url'])

    def test_metadata_image_through_conductor(self):
        # There should be no links here, should default to None
        self.INSTANCE_PROPERTIES['image'] = {'id': 1}
        self.instance = FauxInstance(**self.INSTANCE_PROPERTIES)
        md = util._get_metadata_from_object(self.CONF, self.instance)
        self.assertEqual(1, md['image_ref'])
        self.assertIsNone(md['image_ref_url'])
