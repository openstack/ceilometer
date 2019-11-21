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

"""Tests for ceilometer/polling/non_openstack_dynamic_pollster.py
"""
import copy
import sys

import mock
import requests

from ceilometer.declarative import DynamicPollsterDefinitionException
from ceilometer.declarative import NonOpenStackApisDynamicPollsterException
from ceilometer.polling.dynamic_pollster import DynamicPollster
from ceilometer.polling.non_openstack_dynamic_pollster\
    import NonOpenStackApisDynamicPollster

from oslotest import base


class TestNonOpenStackApisDynamicPollster(base.BaseTestCase):

    class FakeResponse(object):
        status_code = None
        json_object = None

        def json(self):
            return self.json_object

        def raise_for_status(self):
            raise requests.HTTPError("Mock HTTP error.", response=self)

    def setUp(self):
        super(TestNonOpenStackApisDynamicPollster, self).setUp()
        self.pollster_definition_only_required_fields = {
            'name': "test-pollster", 'sample_type': "gauge", 'unit': "test",
            'value_attribute': "volume",
            'url_path': "v1/test/endpoint/fake", 'module': "module-name",
            'authentication_object': "authentication_object"}

        self.pollster_definition_all_fields = {
            'name': "test-pollster", 'sample_type': "gauge", 'unit': "test",
            'value_attribute': "volume",
            'url_path': "v1/test/endpoint/fake", 'module': "module-name",
            'authentication_object': "authentication_object",
            'user_id_attribute': 'user_id',
            'project_id_attribute': 'project_id',
            'resource_id_attribute': 'id', 'barbican_secret_id': 'barbican_id',
            'authentication_parameters': 'parameters'}

    def test_all_fields(self):
        pollster = NonOpenStackApisDynamicPollster(
            self.pollster_definition_only_required_fields)

        all_required = ['module', 'authentication_object', 'name',
                        'sample_type', 'unit', 'value_attribute',
                        'url_path']

        all_optional = ['metadata_fields', 'skip_sample_values',
                        'value_mapping', 'default_value', 'metadata_mapping',
                        'preserve_mapped_metadata', 'user_id_attribute',
                        'project_id_attribute', 'resource_id_attribute',
                        'barbican_secret_id', 'authentication_parameters',
                        'response_entries_key'] + all_required

        for field in all_required:
            self.assertIn(field, pollster.REQUIRED_POLLSTER_FIELDS)

        for field in all_optional:
            self.assertIn(field, pollster.ALL_POLLSTER_FIELDS)

    def test_all_required_fields_exceptions(self):
        pollster = NonOpenStackApisDynamicPollster(
            self.pollster_definition_only_required_fields)

        for key in pollster.REQUIRED_POLLSTER_FIELDS:
            pollster_definition = copy.deepcopy(
                self.pollster_definition_only_required_fields)
            pollster_definition.pop(key)
            exception = self.assertRaises(DynamicPollsterDefinitionException,
                                          NonOpenStackApisDynamicPollster,
                                          pollster_definition)
            self.assertEqual("Required fields ['%s'] not specified."
                             % key, exception.brief_message)

    def test_set_default_values(self):
        pollster = NonOpenStackApisDynamicPollster(
            self.pollster_definition_only_required_fields)

        pollster_definitions = pollster.pollster_definitions

        self.assertEqual(None, pollster_definitions['user_id_attribute'])
        self.assertEqual(None, pollster_definitions['project_id_attribute'])
        self.assertEqual(None, pollster_definitions['resource_id_attribute'])
        self.assertEqual('', pollster_definitions['barbican_secret_id'])
        self.assertEqual('', pollster_definitions['authentication_parameters'])

    def test_user_set_optional_parameters(self):
        pollster = NonOpenStackApisDynamicPollster(
            self.pollster_definition_all_fields)
        pollster_definitions = pollster.pollster_definitions

        self.assertEqual('user_id',
                         pollster_definitions['user_id_attribute'])
        self.assertEqual('project_id',
                         pollster_definitions['project_id_attribute'])
        self.assertEqual('id',
                         pollster_definitions['resource_id_attribute'])
        self.assertEqual('barbican_id',
                         pollster_definitions['barbican_secret_id'])
        self.assertEqual('parameters',
                         pollster_definitions['authentication_parameters'])

    def test_default_discovery_empty_secret_id(self):
        pollster = NonOpenStackApisDynamicPollster(
            self.pollster_definition_only_required_fields)

        self.assertEqual("barbican:", pollster.default_discovery)

    def test_default_discovery_not_empty_secret_id(self):
        pollster = NonOpenStackApisDynamicPollster(
            self.pollster_definition_all_fields)

        self.assertEqual("barbican:barbican_id", pollster.default_discovery)

    @mock.patch('requests.get')
    def test_internal_execute_request_get_samples_status_code_ok(
            self, get_mock):
        sys.modules['module-name'] = mock.MagicMock()

        pollster = NonOpenStackApisDynamicPollster(
            self.pollster_definition_only_required_fields)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value.json_object = {}
        return_value.reason = "Ok"

        get_mock.return_value = return_value

        kwargs = {'resource': "credentials"}

        resp, url = pollster.internal_execute_request_get_samples(kwargs)

        self.assertEqual(
            self.pollster_definition_only_required_fields['url_path'], url)
        self.assertEqual(return_value, resp)

    @mock.patch('requests.get')
    def test_internal_execute_request_get_samples_status_code_not_ok(
            self, get_mock):
        sys.modules['module-name'] = mock.MagicMock()

        pollster = NonOpenStackApisDynamicPollster(
            self.pollster_definition_only_required_fields)

        for http_status_code in requests.status_codes._codes.keys():
            if http_status_code >= 400:
                return_value = self.FakeResponse()
                return_value.status_code = http_status_code
                return_value.json_object = {}
                return_value.reason = requests.status_codes._codes[
                    http_status_code][0]

                get_mock.return_value = return_value

                kwargs = {'resource': "credentials"}
                exception = self.assertRaises(
                    NonOpenStackApisDynamicPollsterException,
                    pollster.internal_execute_request_get_samples, kwargs)

                self.assertEqual(
                    "NonOpenStackApisDynamicPollsterException"
                    " None: Error while executing request[%s]."
                    " Status[%s] and reason [%s]."
                    %
                    (self.pollster_definition_only_required_fields['url_path'],
                     http_status_code, return_value.reason), str(exception))

    def test_generate_new_attributes_in_sample_attribute_key_none(self):
        pollster = NonOpenStackApisDynamicPollster(
            self.pollster_definition_only_required_fields)

        sample = {"test": "2"}
        new_key = "new-key"

        pollster.generate_new_attributes_in_sample(sample, None, new_key)
        pollster.generate_new_attributes_in_sample(sample, "", new_key)

        self.assertNotIn(new_key, sample)

    def test_generate_new_attributes_in_sample(self):
        pollster = NonOpenStackApisDynamicPollster(
            self.pollster_definition_only_required_fields)

        sample = {"test": "2"}
        new_key = "new-key"

        pollster.generate_new_attributes_in_sample(sample, "test", new_key)

        self.assertIn(new_key, sample)
        self.assertEqual(sample["test"], sample[new_key])

    def test_execute_request_get_samples_non_empty_keys(self):
        sample = {'user_id_attribute': "123456789",
                  'project_id_attribute': "dfghyt432345t",
                  'resource_id_attribute': "sdfghjt543"}

        def execute_request_get_samples_mock(self, **kwargs):
            samples = [sample]
            return samples

        DynamicPollster.execute_request_get_samples =\
            execute_request_get_samples_mock

        self.pollster_definition_all_fields[
            'user_id_attribute'] = 'user_id_attribute'
        self.pollster_definition_all_fields[
            'project_id_attribute'] = 'project_id_attribute'
        self.pollster_definition_all_fields[
            'resource_id_attribute'] = 'resource_id_attribute'

        pollster = NonOpenStackApisDynamicPollster(
            self.pollster_definition_all_fields)

        params = {"d": "d"}
        response = pollster.execute_request_get_samples(**params)

        self.assertEqual(sample['user_id_attribute'],
                         response[0]['user_id'])
        self.assertEqual(sample['project_id_attribute'],
                         response[0]['project_id'])
        self.assertEqual(sample['resource_id_attribute'],
                         response[0]['id'])

    def test_execute_request_get_samples_empty_keys(self):
        sample = {'user_id_attribute': "123456789",
                  'project_id_attribute': "dfghyt432345t",
                  'resource_id_attribute': "sdfghjt543"}

        def execute_request_get_samples_mock(self, **kwargs):
            samples = [sample]
            return samples

        DynamicPollster.execute_request_get_samples =\
            execute_request_get_samples_mock

        self.pollster_definition_all_fields[
            'user_id_attribute'] = None
        self.pollster_definition_all_fields[
            'project_id_attribute'] = None
        self.pollster_definition_all_fields[
            'resource_id_attribute'] = None

        pollster = NonOpenStackApisDynamicPollster(
            self.pollster_definition_all_fields)

        params = {"d": "d"}
        response = pollster.execute_request_get_samples(**params)

        self.assertNotIn('user_id', response[0])
        self.assertNotIn('project_id', response[0])
        self.assertNotIn('id', response[0])
