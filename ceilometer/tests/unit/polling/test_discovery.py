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
"""Tests for ceilometer/central/manager.py"""

from unittest import mock

from ceilometer.polling.discovery import endpoint
from ceilometer.polling.discovery import localnode
from ceilometer.polling.discovery import tenant as project
from ceilometer import service
from ceilometer.tests import base
from ceilometer.tests.unit import fakes


class TestEndpointDiscovery(base.BaseTestCase):

    def setUp(self):
        super().setUp()
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
                              service_name=None,
                              interface='publicURL',
                              region_name='test-region-name')]
        self.assertEqual(expected, self.catalog.get_urls.call_args_list)

    def test_keystone_called_no_service_type(self):
        self.discovery.discover(self.manager)
        expected = [mock.call(service_type=None,
                              service_name=None,
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
        super().setUp()
        self.conf = service.prepare_service([], [])
        self.discovery = localnode.LocalNodeDiscovery(self.conf)
        self.manager = mock.MagicMock()

    def test_lockalnode_discovery(self):
        self.assertEqual([self.conf.host],
                         self.discovery.discover(self.manager))


class TestProjectDiscovery(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.CONF = service.prepare_service([], [])

        self.discovery = project.TenantDiscovery(self.CONF)
        self.manager = mock.MagicMock()
        # Wrap FakeKeystoneClient so that we can check the expected calls
        self.manager.keystone = mock.Mock(wraps=fakes.FakeKeystoneClient())

    def test_project_discovery(self):
        result = self.discovery.discover(self.manager)
        self.assertEqual(len(result), 4)
        self.manager.keystone.domains.list.assert_called_once_with()
        self.assertEqual(
            self.manager.keystone.projects.list.mock_calls,
            [mock.call(d) for d in fakes.DEFAULT_DOMAINS])

    def test_project_discovery_ignore_disabled_projects(self):
        self.CONF.set_override("ignore_disabled_projects",
                               True, group="polling")
        result = self.discovery.discover(self.manager)
        self.assertEqual(len(result), 3)
        self.manager.keystone.domains.list.assert_called_once_with(
            enabled=True)
        self.assertEqual(
            self.manager.keystone.projects.list.mock_calls,
            [mock.call(d, enabled=True) for d in fakes.DEFAULT_DOMAINS])
