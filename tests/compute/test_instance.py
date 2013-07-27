# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Tests for ceilometer.compute.instance
"""

import unittest

import mock

from ceilometer.compute import instance
from ceilometer.compute import manager


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


class TestLocationMetadata(unittest.TestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        self.manager = manager.AgentManager()
        super(TestLocationMetadata, self).setUp()

        # Mimics an instance returned from nova api call
        self.INSTANCE_PROPERTIES = {'name': 'display name',
                                    'OS-EXT-SRV-ATTR:instance_name':
                                    'instance-000001',
                                    'availability_zone': None,
                                    'OS-EXT-AZ:availability_zone':
                                    'foo-zone',
                                    'reservation_id': 'reservation id',
                                    'architecture': 'x86_64',
                                    'kernel_id': 'kernel id',
                                    'os_type': 'linux',
                                    'ramdisk_id': 'ramdisk id',
                                    'ephemeral_gb': 7,
                                    'root_gb': 3,
                                    'image': {'id': 1,
                                              'links': [{"rel": "bookmark",
                                                         'href': 2}]},
                                    'hostId': '1234-5678',
                                    'flavor': {'id': 1,
                                               'disk': 0,
                                               'ram': 512,
                                               'vcpus': 2},
                                    'metadata': {'metering.autoscale.group':
                                                 'X' * 512,
                                                 'metering.ephemeral_gb': 42}}

        self.instance = FauxInstance(**self.INSTANCE_PROPERTIES)

    def test_metadata(self):
        md = instance.get_metadata_from_object(self.instance)
        iprops = self.INSTANCE_PROPERTIES
        self.assertEqual(md['availability_zone'],
                         iprops['OS-EXT-AZ:availability_zone'])
        self.assertEqual(md['name'], iprops['OS-EXT-SRV-ATTR:instance_name'])
        self.assertEqual(md['disk_gb'], iprops['flavor']['disk'])
        self.assertEqual(md['display_name'], iprops['name'])
        self.assertEqual(md['instance_type'], iprops['flavor']['id'])
        self.assertEqual(md['image_ref'], iprops['image']['id'])
        self.assertEqual(md['image_ref_url'],
                         iprops['image']['links'][0]['href'])
        self.assertEqual(md['memory_mb'], iprops['flavor']['ram'])
        self.assertEqual(md['vcpus'], iprops['flavor']['vcpus'])
        self.assertEqual(md['host'], iprops['hostId'])

        self.assertEqual(md['reservation_id'], iprops['reservation_id'])
        self.assertEqual(md['kernel_id'], iprops['kernel_id'])
        self.assertEqual(md['ramdisk_id'], iprops['ramdisk_id'])
        self.assertEqual(md['architecture'], iprops['architecture'])
        self.assertEqual(md['os_type'], iprops['os_type'])
        self.assertEqual(md['ephemeral_gb'], iprops['ephemeral_gb'])
        self.assertEqual(md['root_gb'], iprops['root_gb'])

    def test_metadata_empty_image(self):
        self.INSTANCE_PROPERTIES['image'] = ''
        self.instance = FauxInstance(**self.INSTANCE_PROPERTIES)
        md = instance.get_metadata_from_object(self.instance)
        self.assertEqual(md['image_ref'], None)
        self.assertEqual(md['image_ref_url'], None)
