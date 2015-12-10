#
# Copyright 2014 Red Hat Inc.
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
"""Tests for ceilometer/central/manager.py
"""

import mock
from oslo_config import fixture as fixture_config
from oslotest import base

from ceilometer.agent.discovery import endpoint
from ceilometer.agent.discovery import localnode
from ceilometer.hardware import discovery as hardware


class TestEndpointDiscovery(base.BaseTestCase):

    def setUp(self):
        super(TestEndpointDiscovery, self).setUp()
        self.discovery = endpoint.EndpointDiscovery()
        self.manager = mock.MagicMock()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.CONF.set_override('interface', 'test-endpoint-type',
                               group='service_credentials')
        self.CONF.set_override('region_name', 'test-region-name',
                               group='service_credentials')
        self.catalog = (self.manager.keystone.session.auth.get_access.
                        return_value.service_catalog)

    def test_keystone_called(self):
        self.discovery.discover(self.manager, param='test-service-type')
        expected = [mock.call(service_type='test-service-type',
                              interface='test-endpoint-type',
                              region_name='test-region-name')]
        self.assertEqual(expected, self.catalog.get_urls.call_args_list)

    def test_keystone_called_no_service_type(self):
        self.discovery.discover(self.manager)
        expected = [mock.call(service_type=None,
                              interface='test-endpoint-type',
                              region_name='test-region-name')]
        self.assertEqual(expected,
                         self.catalog.get_urls
                         .call_args_list)

    def test_keystone_called_no_endpoints(self):
        self.catalog.get_urls.return_value = []
        self.assertEqual([], self.discovery.discover(self.manager))


class TestLocalnodeDiscovery(base.BaseTestCase):
    def setUp(self):
        super(TestLocalnodeDiscovery, self).setUp()
        self.discovery = localnode.LocalNodeDiscovery()
        self.manager = mock.MagicMock()

    def test_lockalnode_discovery(self):
        self.assertEqual(['local_host'], self.discovery.discover(self.manager))


class TestHardwareDiscovery(base.BaseTestCase):
    class MockInstance(object):
        addresses = {'ctlplane': [
            {'addr': '0.0.0.0',
             'OS-EXT-IPS-MAC:mac_addr': '01-23-45-67-89-ab'}
        ]}
        id = 'resource_id'
        image = {'id': 'image_id'}
        flavor = {'id': 'flavor_id'}

    expected = {
        'resource_id': 'resource_id',
        'resource_url': 'snmp://ro_snmp_user:password@0.0.0.0',
        'mac_addr': '01-23-45-67-89-ab',
        'image_id': 'image_id',
        'flavor_id': 'flavor_id',
    }

    def setUp(self):
        super(TestHardwareDiscovery, self).setUp()
        self.discovery = hardware.NodesDiscoveryTripleO()
        self.discovery.nova_cli = mock.MagicMock()
        self.manager = mock.MagicMock()

    def test_hardware_discovery(self):
        self.discovery.nova_cli.instance_get_all.return_value = [
            self.MockInstance()]
        resources = self.discovery.discover(self.manager)
        self.assertEqual(1, len(resources))
        self.assertEqual(self.expected, resources[0])

    def test_hardware_discovery_without_flavor(self):
        instance = self.MockInstance()
        instance.flavor = {}
        self.discovery.nova_cli.instance_get_all.return_value = [instance]
        resources = self.discovery.discover(self.manager)
        self.assertEqual(0, len(resources))
