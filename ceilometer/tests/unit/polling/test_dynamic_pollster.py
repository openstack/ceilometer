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


from ceilometer.declarative import DynamicPollsterDefinitionException
from ceilometer.polling import dynamic_pollster
from ceilometer import sample

import copy
import logging
import mock

from oslotest import base

import requests

LOG = logging.getLogger(__name__)


class TestDynamicPollster(base.BaseTestCase):
    class FakeResponse(object):
        status_code = None
        json_object = None

        def json(self):
            return self.json_object

        def raise_for_status(self):
            raise requests.HTTPError("Mock HTTP error.", response=self)

    class FakeManager(object):
        _keystone = None

    def setUp(self):
        super(TestDynamicPollster, self).setUp()
        self.pollster_definition_only_required_fields = {
            'name': "test-pollster", 'sample_type': "gauge", 'unit': "test",
            'value_attribute': "volume", 'endpoint_type': "test",
            'url_path': "v1/test/endpoint/fake"}

        self.pollster_definition_all_fields = {
            'metadata_fields': "metadata-field-name",
            'skip_sample_values': ["I-do-not-want-entries-with-this-value"],
            'value_mapping': {
                'value-to-map': 'new-value', 'value-to-map-to-numeric': 12
            },
            'default_value_mapping': 0,
            'metadata_mapping': {
                'old-metadata-name': "new-metadata-name"
            },
            'preserve_mapped_metadata': False}
        self.pollster_definition_all_fields.update(
            self.pollster_definition_only_required_fields)

    def execute_basic_asserts(self, pollster, pollster_definition):
        self.assertEqual(pollster, pollster.obj)
        self.assertEqual(pollster_definition['name'], pollster.name)

        for key in pollster.REQUIRED_POLLSTER_FIELDS:
            self.assertEqual(pollster_definition[key],
                             pollster.pollster_definitions[key])

        self.assertEqual(pollster_definition, pollster.pollster_definitions)

    def test_all_required_fields_ok(self):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        self.execute_basic_asserts(
            pollster, self.pollster_definition_only_required_fields)

        self.assertEqual(
            0, len(pollster.pollster_definitions['skip_sample_values']))
        self.assertEqual(
            0, len(pollster.pollster_definitions['value_mapping']))
        self.assertEqual(
            -1, pollster.pollster_definitions['default_value'])
        self.assertEqual(
            0, len(pollster.pollster_definitions['metadata_mapping']))
        self.assertEqual(
            True, pollster.pollster_definitions['preserve_mapped_metadata'])

    def test_all_fields_ok(self):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_all_fields)

        self.execute_basic_asserts(pollster,
                                   self.pollster_definition_all_fields)

        self.assertEqual(
            1, len(pollster.pollster_definitions['skip_sample_values']))
        self.assertEqual(
            2, len(pollster.pollster_definitions['value_mapping']))
        self.assertEqual(
            0, pollster.pollster_definitions['default_value_mapping'])
        self.assertEqual(
            1, len(pollster.pollster_definitions['metadata_mapping']))
        self.assertEqual(
            False, pollster.pollster_definitions['preserve_mapped_metadata'])

    def test_all_required_fields_exceptions(self):
        for key in dynamic_pollster.\
                DynamicPollster.REQUIRED_POLLSTER_FIELDS:
            pollster_definition = copy.deepcopy(
                self.pollster_definition_only_required_fields)
            pollster_definition.pop(key)
            exception = self.assertRaises(DynamicPollsterDefinitionException,
                                          dynamic_pollster.DynamicPollster,
                                          pollster_definition)
            self.assertEqual("Required fields ['%s'] not specified."
                             % key, exception.brief_message)

    def test_invalid_sample_type(self):
        self.pollster_definition_only_required_fields[
            'sample_type'] = "invalid_sample_type"
        exception = self.assertRaises(
            DynamicPollsterDefinitionException,
            dynamic_pollster.DynamicPollster,
            self.pollster_definition_only_required_fields)
        self.assertEqual("Invalid sample type [invalid_sample_type]. "
                         "Valid ones are [('gauge', 'delta', 'cumulative')].",
                         exception.brief_message)

    def test_all_valid_sample_type(self):
        for sample_type in sample.TYPES:
            self.pollster_definition_only_required_fields[
                'sample_type'] = sample_type
            pollster = dynamic_pollster.DynamicPollster(
                self.pollster_definition_only_required_fields)

            self.execute_basic_asserts(
                pollster, self.pollster_definition_only_required_fields)

    def test_default_discovery_method(self):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        self.assertEqual("endpoint:test", pollster.default_discovery)

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_execute_request_get_samples_empty_response(self, client_mock):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value.json_object = {}

        client_mock.session.get.return_value = return_value

        samples = pollster.execute_request_get_samples(
            client_mock, "https://endpoint.server.name/")

        self.assertEqual(0, len(samples))

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_execute_request_get_samples_response_non_empty(
            self, client_mock):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value.json_object = {"firstElement": [{}, {}, {}]}

        client_mock.session.get.return_value = return_value

        samples = pollster.execute_request_get_samples(
            client_mock, "https://endpoint.server.name/")

        self.assertEqual(3, len(samples))

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_execute_request_get_samples_exception_on_request(
            self, client_mock):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.bad

        client_mock.session.get.return_value = return_value

        exception = self.assertRaises(requests.HTTPError,
                                      pollster.execute_request_get_samples,
                                      client_mock,
                                      "https://endpoint.server.name/")
        self.assertEqual("Mock HTTP error.", str(exception))

    def test_generate_new_metadata_fields_no_metadata_mapping(self):
        metadata = {'name': 'someName',
                    'value': 1}

        metadata_before_call = copy.deepcopy(metadata)

        self.pollster_definition_only_required_fields['metadata_mapping'] = {}
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)
        pollster.generate_new_metadata_fields(metadata)

        self.assertEqual(metadata_before_call, metadata)

    def test_generate_new_metadata_fields_preserve_old_key(self):
        metadata = {'name': 'someName', 'value': 2}

        expected_metadata = copy.deepcopy(metadata)
        expected_metadata['balance'] = metadata['value']

        self.pollster_definition_only_required_fields[
            'metadata_mapping'] = {'value': 'balance'}
        self.pollster_definition_only_required_fields[
            'preserve_mapped_metadata'] = True
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)
        pollster.generate_new_metadata_fields(metadata)

        self.assertEqual(expected_metadata, metadata)

    def test_generate_new_metadata_fields_preserve_old_key_equals_false(self):
        metadata = {'name': 'someName', 'value': 1}

        expected_clean_metadata = copy.deepcopy(metadata)
        expected_clean_metadata['balance'] = metadata['value']
        expected_clean_metadata.pop('value')

        self.pollster_definition_only_required_fields[
            'metadata_mapping'] = {'value': 'balance'}
        self.pollster_definition_only_required_fields[
            'preserve_mapped_metadata'] = False
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)
        pollster.generate_new_metadata_fields(metadata)

        self.assertEqual(expected_clean_metadata, metadata)

    def test_execute_value_mapping_no_value_mapping(self):
        self.pollster_definition_only_required_fields['value_mapping'] = {}
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        value_to_be_mapped = "test"
        expected_value = value_to_be_mapped
        value = pollster.execute_value_mapping(value_to_be_mapped)

        self.assertEqual(expected_value, value)

    def test_execute_value_mapping_no_value_mapping_found_with_default(self):
        self.pollster_definition_only_required_fields[
            'value_mapping'] = {'some-possible-value': 15}
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        value_to_be_mapped = "test"
        expected_value = -1
        value = pollster.execute_value_mapping(value_to_be_mapped)

        self.assertEqual(expected_value, value)

    def test_execute_value_mapping_no_value_mapping_found_with_custom_default(
            self):
        self.pollster_definition_only_required_fields[
            'value_mapping'] = {'some-possible-value': 5}
        self.pollster_definition_only_required_fields[
            'default_value'] = 0
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        value_to_be_mapped = "test"
        expected_value = 0
        value = pollster.execute_value_mapping(value_to_be_mapped)

        self.assertEqual(expected_value, value)

    def test_execute_value_mapping(self):
        self.pollster_definition_only_required_fields[
            'value_mapping'] = {'test': 'new-value'}
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        value_to_be_mapped = "test"
        expected_value = 'new-value'
        value = pollster.execute_value_mapping(value_to_be_mapped)

        self.assertEqual(expected_value, value)

    def test_get_samples_no_resources(self):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)
        samples = pollster.get_samples(None, None, None)

        self.assertEqual(None, next(samples))

    @mock.patch('ceilometer.polling.dynamic_pollster.'
                'DynamicPollster.execute_request_get_samples')
    def test_get_samples_empty_samples(self, execute_request_get_samples_mock):
        execute_request_get_samples_mock.side_effect = []

        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        fake_manager = self.FakeManager()
        samples = pollster.get_samples(
            fake_manager, None, ["https://endpoint.server.name.com/"])

        samples_list = list()
        try:
            for s in samples:
                samples_list.append(s)
        except RuntimeError as e:
            LOG.debug("Generator threw a StopIteration "
                      "and we need to catch it [%s]." % e)

        self.assertEqual(0, len(samples_list))

    def fake_sample_list(self, keystone_client=None, endpoint=None):
        samples_list = list()
        samples_list.append(
            {'name': "sample5", 'volume': 5, 'description': "desc-sample-5",
             'user_id': "924d1f77-5d75-4b96-a755-1774d6be17af",
             'project_id': "6c7a0e87-7f2e-45d3-89ca-5a2dbba71a0e",
             'id': "e335c317-dfdd-4f22-809a-625bd9a5992d"
             }
        )
        samples_list.append(
            {'name': "sample1", 'volume': 2, 'description': "desc-sample-2",
             'user_id': "20b5a704-b481-4603-a99e-2636c144b876",
             'project_id': "6c7a0e87-7f2e-45d3-89ca-5a2dbba71a0e",
             'id': "2e350554-6c05-4fda-8109-e47b595a714c"
             }
        )
        return samples_list

    @mock.patch.object(
        dynamic_pollster.DynamicPollster,
        'execute_request_get_samples',
        fake_sample_list)
    def test_get_samples(self):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        fake_manager = self.FakeManager()
        samples = pollster.get_samples(
            fake_manager, None, ["https://endpoint.server.name.com/"])

        samples_list = list(samples)
        self.assertEqual(2, len(samples_list))

        first_element = [
            s for s in samples_list
            if s.resource_id == "e335c317-dfdd-4f22-809a-625bd9a5992d"][0]
        self.assertEqual(5, first_element.volume)
        self.assertEqual(
            "6c7a0e87-7f2e-45d3-89ca-5a2dbba71a0e", first_element.project_id)
        self.assertEqual(
            "924d1f77-5d75-4b96-a755-1774d6be17af", first_element.user_id)

        second_element = [
            s for s in samples_list
            if s.resource_id == "2e350554-6c05-4fda-8109-e47b595a714c"][0]
        self.assertEqual(2, second_element.volume)
        self.assertEqual(
            "6c7a0e87-7f2e-45d3-89ca-5a2dbba71a0e", second_element.project_id)
        self.assertEqual(
            "20b5a704-b481-4603-a99e-2636c144b876", second_element.user_id)
