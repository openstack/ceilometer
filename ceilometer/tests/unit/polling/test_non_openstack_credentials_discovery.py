# Copyright 2014-2015 Red Hat, Inc
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
import requests

from ceilometer.polling.discovery.endpoint import EndpointDiscovery
from ceilometer.polling.discovery.non_openstack_credentials_discovery import \
    NonOpenStackCredentialsDiscovery


class TestNonOpenStackCredentialsDiscovery(base.BaseTestCase):

    class FakeResponse(object):
        status_code = None
        json_object = None
        _content = ""

        def json(self):
            return self.json_object

        def raise_for_status(self):
            raise requests.HTTPError("Mock HTTP error.", response=self)

    class FakeManager(object):
        def __init__(self, keystone_client_mock):
            self._keystone = keystone_client_mock

    def setUp(self):
        super(TestNonOpenStackCredentialsDiscovery, self).setUp()

        self.discovery = NonOpenStackCredentialsDiscovery(None)

    def test_discover_no_parameters(self):
        result = self.discovery.discover(None, None)

        self.assertEqual(['No secrets found'], result)

        result = self.discovery.discover(None, "")

        self.assertEqual(['No secrets found'], result)

    def test_discover_no_barbican_endpoint(self):
        def discover_mock(self, manager, param=None):
            return []

        original_discover_method = EndpointDiscovery.discover
        EndpointDiscovery.discover = discover_mock

        result = self.discovery.discover(None, "param")

        self.assertEqual(['No secrets found'], result)

        EndpointDiscovery.discover = original_discover_method

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_discover_error_response(self, client_mock):
        def discover_mock(self, manager, param=None):
            return ["barbican_url"]

        original_discover_method = EndpointDiscovery.discover
        EndpointDiscovery.discover = discover_mock

        for http_status_code in requests.status_codes._codes.keys():
            if http_status_code < 400:
                continue

            return_value = self.FakeResponse()
            return_value.status_code = http_status_code
            return_value.json_object = {}

            client_mock.session.get.return_value = return_value

            exception = self.assertRaises(
                requests.HTTPError,
                self.discovery.discover,
                manager=self.FakeManager(client_mock),
                param="param")

            self.assertEqual("Mock HTTP error.", str(exception))

        EndpointDiscovery.discover = original_discover_method

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_discover_response_ok(self, client_mock):
        discover_mock = mock.MagicMock()
        discover_mock.return_value = ["barbican_url"]

        original_discover_method = EndpointDiscovery.discover
        EndpointDiscovery.discover = discover_mock

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value.json_object = {}
        return_value._content = "content"

        client_mock.session.get.return_value = return_value

        fake_manager = self.FakeManager(client_mock)
        response = self.discovery.discover(manager=fake_manager, param="param")

        self.assertEqual(["content"], response)

        discover_mock.assert_has_calls([
            mock.call(fake_manager, "key-manager")])
        EndpointDiscovery.discover = original_discover_method
