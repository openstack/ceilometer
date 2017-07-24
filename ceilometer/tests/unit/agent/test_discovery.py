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
from oslotest import base

from ceilometer.agent.discovery import endpoint
from ceilometer.agent.discovery import localnode
from ceilometer.agent.discovery import tenant as project
from ceilometer.hardware import discovery as hardware
from ceilometer import service


class TestEndpointDiscovery(base.BaseTestCase):

    def setUp(self):
        super(TestEndpointDiscovery, self).setUp()
        CONF = service.prepare_service([], [])
        CONF.set_override('interface', 'publicURL',
                          group='service_credentials')
        CONF.set_override('region_name', 'test-region-name',
                          group='service_credentials')
        self.discovery = endpoint.EndpointDiscovery(CONF)
        self.manager = mock.MagicMock()
        self.catalog = (self.manager.keystone.session.auth.get_access.
                        return_value.service_catalog)

    def test_keystone_called(self):
        self.discovery.discover(self.manager, param='test-service-type')
        expected = [mock.call(service_type='test-service-type',
                              interface='publicURL',
                              region_name='test-region-name')]
        self.assertEqual(expected, self.catalog.get_urls.call_args_list)

    def test_keystone_called_no_service_type(self):
        self.discovery.discover(self.manager)
        expected = [mock.call(service_type=None,
                              interface='publicURL',
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
        CONF = service.prepare_service([], [])
        self.discovery = localnode.LocalNodeDiscovery(CONF)
        self.manager = mock.MagicMock()

    def test_lockalnode_discovery(self):
        self.assertEqual(['local_host'], self.discovery.discover(self.manager))


class TestProjectDiscovery(base.BaseTestCase):
    def prepare_mock_data(self):
        domain_heat = mock.MagicMock()
        domain_heat.id = '2f42ab40b7ad4140815ef830d816a16c'
        domain_heat.name = 'heat'
        domain_heat.enabled = True
        domain_heat.links = {
            u'self': u'http://192.168.1.1/identity/v3/domains/'
                     u'2f42ab40b7ad4140815ef830d816a16c'}

        domain_default = mock.MagicMock()
        domain_default.id = 'default'
        domain_default.name = 'Default'
        domain_default.enabled = True
        domain_default.links = {
            u'self': u'http://192.168.1.1/identity/v3/domains/default'}

        project_admin = mock.MagicMock()
        project_admin.id = '2ce92449a23145ef9c539f3327960ce3'
        project_admin.name = 'admin'
        project_admin.parent_id = 'default'
        project_admin.domain_id = 'default'
        project_admin.is_domain = False
        project_admin.enabled = True
        project_admin.links = {
            u'self': u'http://192.168.4.46/identity/v3/projects/'
                     u'2ce92449a23145ef9c539f3327960ce3'},

        project_service = mock.MagicMock()
        project_service.id = '9bf93b86bca04e3b815f86a5de083adc'
        project_service.name = 'service'
        project_service.parent_id = 'default'
        project_service.domain_id = 'default'
        project_service.is_domain = False
        project_service.enabled = True
        project_service.links = {
            u'self': u'http://192.168.4.46/identity/v3/projects/'
                     u'9bf93b86bca04e3b815f86a5de083adc'}

        project_demo = mock.MagicMock()
        project_demo.id = '57d96b9af18d43bb9d047f436279b0be'
        project_demo.name = 'demo'
        project_demo.parent_id = 'default'
        project_demo.domain_id = 'default'
        project_demo.is_domain = False
        project_demo.enabled = True
        project_demo.links = {
            u'self': u'http://192.168.4.46/identity/v3/projects/'
                     u'57d96b9af18d43bb9d047f436279b0be'}

        self.domains = [domain_heat, domain_default]
        self.default_domain_projects = [project_admin, project_service]
        self.heat_domain_projects = [project_demo]

    def side_effect(self, domain=None):
        if not domain or domain.name == 'Default':
            return self.default_domain_projects
        elif domain.name == 'heat':
            return self.heat_domain_projects
        else:
            return []

    def setUp(self):
        super(TestProjectDiscovery, self).setUp()
        CONF = service.prepare_service([], [])
        self.discovery = project.TenantDiscovery(CONF)
        self.prepare_mock_data()
        self.manager = mock.MagicMock()
        self.manager.keystone.projects.list.side_effect = self.side_effect

    def test_project_discovery_with_domains(self):
        self.manager.keystone.domains.list.return_value = self.domains
        result = self.discovery.discover(self.manager)
        self.assertEqual(len(result), 3)
        self.assertEqual(self.manager.keystone.projects.list.call_count, 2)

    def test_project_discovery_no_domain(self):
        self.manager.keystone.domains.list.return_value = []
        result = self.discovery.discover(self.manager)
        self.assertEqual(len(result), 2)
        self.assertEqual(self.manager.keystone.projects.list.call_count, 1)


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

    expected_usm = {
        'resource_id': 'resource_id',
        'resource_url': ''.join(['snmp://ro_snmp_user:password@0.0.0.0',
                                 '?priv_proto=aes192',
                                 '&priv_password=priv_pass']),
        'mac_addr': '01-23-45-67-89-ab',
        'image_id': 'image_id',
        'flavor_id': 'flavor_id',
    }

    def setUp(self):
        super(TestHardwareDiscovery, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.discovery = hardware.NodesDiscoveryTripleO(self.CONF)
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

    def test_hardware_discovery_usm(self):
        self.CONF.set_override('readonly_user_priv_proto', 'aes192',
                               group='hardware')
        self.CONF.set_override('readonly_user_priv_password', 'priv_pass',
                               group='hardware')
        self.discovery.nova_cli.instance_get_all.return_value = [
            self.MockInstance()]
        resources = self.discovery.discover(self.manager)
        self.assertEqual(self.expected_usm, resources[0])
