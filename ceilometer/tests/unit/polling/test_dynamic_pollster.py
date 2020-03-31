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

"""Tests for ceilometer/polling/dynamic_pollster.py"""
import copy
import logging
from unittest import mock

from oslotest import base
import requests

from ceilometer.declarative import DynamicPollsterDefinitionException
from ceilometer.polling import dynamic_pollster
from ceilometer import sample

LOG = logging.getLogger(__name__)


REQUIRED_POLLSTER_FIELDS = ['name', 'sample_type', 'unit',
                            'value_attribute', 'endpoint_type',
                            'url_path']


class SampleGenerator(object):

    def __init__(self, samples_dict, turn_to_list=False):
        self.turn_to_list = turn_to_list
        self.samples_dict = {}
        for k, v in samples_dict.items():
            if isinstance(v, list):
                self.samples_dict[k] = [0, v]
            else:
                self.samples_dict[k] = [0, [v]]

    def get_next_sample_dict(self):
        _dict = {}
        for key in self.samples_dict.keys():
            _dict[key] = self.get_next_sample(key)

        if self.turn_to_list:
            _dict = [_dict]
        return _dict

    def get_next_sample(self, key):
        samples = self.samples_dict[key][1]
        samples_next_iteration = self.samples_dict[key][0] % len(samples)
        self.samples_dict[key][0] += 1
        _sample = samples[samples_next_iteration]
        if isinstance(_sample, SampleGenerator):
            return _sample.get_next_sample_dict()
        return _sample


class PagedSamplesGenerator(SampleGenerator):

    def __init__(self, samples_dict, dict_name, page_link_name):
        super(PagedSamplesGenerator, self).__init__(samples_dict)
        self.dict_name = dict_name
        self.page_link_name = page_link_name
        self.response = {}

    def generate_samples(self, page_base_link, page_links, last_page_size):
        self.response.clear()
        current_page_link = page_base_link
        for page_link, page_size in page_links.items():
            page_link = page_base_link + "/" + page_link
            self.response[current_page_link] = {
                self.page_link_name: page_link,
                self.dict_name: self.populate_page(page_size)
            }
            current_page_link = page_link

        self.response[current_page_link] = {
            self.dict_name: self.populate_page(last_page_size)
        }

    def populate_page(self, page_size):
        page = []
        for item_number in range(0, page_size):
            page.append(self.get_next_sample_dict())

        return page


class PagedSamplesGeneratorHttpRequestMock(PagedSamplesGenerator):

    def mock_request(self, url, **kwargs):
        return_value = TestDynamicPollster.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value.json_object = self.response[url]

        return return_value


class TestDynamicPollster(base.BaseTestCase):
    class FakeResponse(object):
        status_code = None
        json_object = None

        def json(self):
            return self.json_object

        def raise_for_status(self):
            raise requests.HTTPError("Mock HTTP error.", response=self)

    class FakeManager(object):
        def __init__(self, keystone=None):
            self._keystone = keystone

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

        self.multi_metric_pollster_definition = {
            'name': "test-pollster.{category}", 'sample_type': "gauge",
            'unit': "test", 'value_attribute': "[categories].ops",
            'endpoint_type': "test", 'url_path': "v1/test/endpoint/fake"}

    def execute_basic_asserts(self, pollster, pollster_definition):
        self.assertEqual(pollster, pollster.obj)
        self.assertEqual(pollster_definition['name'], pollster.name)

        for key in REQUIRED_POLLSTER_FIELDS:
            self.assertEqual(pollster_definition[key],
                             pollster.pollster_definitions[key])

        self.assertEqual(pollster_definition, pollster.pollster_definitions)

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_skip_samples(self, keystone_mock):
        generator = PagedSamplesGeneratorHttpRequestMock(samples_dict={
            'volume': SampleGenerator(samples_dict={
                'name': ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
                'tmp': ['ra', 'rb', 'rc', 'rd', 're', 'rf', 'rg', 'rh']},
                turn_to_list=True),
            'id': [1, 2, 3, 4, 5, 6, 7, 8],
            'name': ['a1', 'b2', 'c3', 'd4', 'e5', 'f6', 'g7', 'h8']
        }, dict_name='servers', page_link_name='server_link')

        generator.generate_samples('http://test.com/v1/test-volumes', {
            'marker=c3': 3,
            'marker=f6': 3
        }, 2)

        keystone_mock.session.get.side_effect = generator.mock_request
        fake_manager = self.FakeManager(keystone=keystone_mock)

        pollster_definition = dict(self.multi_metric_pollster_definition)
        pollster_definition['name'] = 'test-pollster.{name}'
        pollster_definition['value_attribute'] = '[volume].tmp'
        pollster_definition['skip_sample_values'] = ['rb']
        pollster_definition['url_path'] = 'v1/test-volumes'
        pollster_definition['response_entries_key'] = 'servers'
        pollster = dynamic_pollster.DynamicPollster(pollster_definition)
        samples = pollster.get_samples(fake_manager, None, ['http://test.com'])
        self.assertEqual(['ra', 'rc'], list(map(lambda s: s.volume, samples)))

        pollster_definition['name'] = 'test-pollster'
        pollster_definition['value_attribute'] = 'name'
        pollster_definition['skip_sample_values'] = ['b2']
        pollster = dynamic_pollster.DynamicPollster(pollster_definition)
        samples = pollster.get_samples(fake_manager, None, ['http://test.com'])
        self.assertEqual(['a1', 'c3'], list(map(lambda s: s.volume, samples)))

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
        for key in REQUIRED_POLLSTER_FIELDS:
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

        self.assertEqual("endpoint:test", pollster.definitions.sample_gatherer
                         .default_discovery)

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_execute_request_get_samples_empty_response(self, client_mock):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value.json_object = {}

        client_mock.session.get.return_value = return_value

        samples = pollster.definitions.sample_gatherer. \
            execute_request_get_samples(
                keystone_client=client_mock,
                resource="https://endpoint.server.name/")

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

        samples = pollster.definitions.sample_gatherer. \
            execute_request_get_samples(
                keystone_client=client_mock,
                resource="https://endpoint.server.name/")

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
                                      pollster.definitions.sample_gatherer.
                                      execute_request_get_samples,
                                      keystone_client=client_mock,
                                      resource="https://endpoint.server.name/")
        self.assertEqual("Mock HTTP error.", str(exception))

    def test_generate_new_metadata_fields_no_metadata_mapping(self):
        metadata = {'name': 'someName',
                    'value': 1}

        metadata_before_call = copy.deepcopy(metadata)

        self.pollster_definition_only_required_fields['metadata_mapping'] = {}
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)
        pollster.definitions.sample_extractor.generate_new_metadata_fields(
            metadata, self.pollster_definition_only_required_fields)

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
        pollster.definitions.sample_extractor.generate_new_metadata_fields(
            metadata, self.pollster_definition_only_required_fields)

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
        pollster.definitions.sample_extractor.generate_new_metadata_fields(
            metadata, self.pollster_definition_only_required_fields)

        self.assertEqual(expected_clean_metadata, metadata)

    def test_execute_value_mapping_no_value_mapping(self):
        self.pollster_definition_only_required_fields['value_mapping'] = {}
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        value_to_be_mapped = "test"
        expected_value = value_to_be_mapped
        value = pollster.definitions.value_mapper. \
            execute_value_mapping(value_to_be_mapped)

        self.assertEqual(expected_value, value)

    def test_execute_value_mapping_no_value_mapping_found_with_default(self):
        self.pollster_definition_only_required_fields[
            'value_mapping'] = {'some-possible-value': 15}
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        value_to_be_mapped = "test"
        expected_value = -1
        value = pollster.definitions.value_mapper. \
            execute_value_mapping(value_to_be_mapped)

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
        value = pollster.definitions.value_mapper. \
            execute_value_mapping(value_to_be_mapped)

        self.assertEqual(expected_value, value)

    def test_execute_value_mapping(self):
        self.pollster_definition_only_required_fields[
            'value_mapping'] = {'test': 'new-value'}
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        value_to_be_mapped = "test"
        expected_value = 'new-value'
        value = pollster.definitions.value_mapper. \
            execute_value_mapping(value_to_be_mapped)

        self.assertEqual(expected_value, value)

    def test_get_samples_no_resources(self):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)
        samples = pollster.get_samples(None, None, None)

        self.assertEqual(None, next(samples))

    @mock.patch('ceilometer.polling.dynamic_pollster.'
                'PollsterSampleGatherer.execute_request_get_samples')
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

    def fake_sample_list(self, keystone_client=None, resource=None):
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
        dynamic_pollster.PollsterSampleGatherer,
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

    def test_retrieve_entries_from_response_response_is_a_list(self):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        response = [{"object1-attr1": 1}, {"object1-attr2": 2}]
        entries = pollster.definitions.sample_gatherer. \
            retrieve_entries_from_response(response)

        self.assertEqual(response, entries)

    def test_retrieve_entries_using_first_entry_from_response(self):
        self.pollster_definition_only_required_fields[
            'response_entries_key'] = "first"

        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        first_entries_from_response = [{"object1-attr1": 1},
                                       {"object1-attr2": 2}]
        second_entries_from_response = [{"object1-attr3": 3},
                                        {"object1-attr4": 33}]

        response = {"first": first_entries_from_response,
                    "second": second_entries_from_response}
        entries = pollster.definitions.sample_gatherer. \
            retrieve_entries_from_response(response)

        self.assertEqual(first_entries_from_response, entries)

    def test_retrieve_entries_using_second_entry_from_response(self):
        self.pollster_definition_only_required_fields[
            'response_entries_key'] = "second"
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        first_entries_from_response = [{"object1-attr1": 1},
                                       {"object1-attr2": 2}]
        second_entries_from_response = [{"object1-attr3": 3},
                                        {"object1-attr4": 33}]

        response = {"first": first_entries_from_response,
                    "second": second_entries_from_response}
        entries = pollster.definitions.sample_gatherer. \
            retrieve_entries_from_response(response)

        self.assertEqual(second_entries_from_response, entries)

    def test_retrieve_attribute_nested_value_non_nested_key(self):
        key = "key"
        value = [{"d": 2}, {"g": {"h": "val"}}]

        json_object = {"key": value}

        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        returned_value = pollster.definitions.sample_extractor.\
            retrieve_attribute_nested_value(json_object, key)

        self.assertEqual(value, returned_value)

    def test_retrieve_attribute_nested_value_nested_key(self):
        key = "key.subKey"

        value1 = [{"d": 2}, {"g": {"h": "val"}}]
        sub_value = [{"r": 245}, {"h": {"yu": "yu"}}]

        json_object = {"key": {"subKey": sub_value, "subkey2": value1}}

        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        returned_value = pollster.definitions.sample_extractor. \
            retrieve_attribute_nested_value(json_object, key)

        self.assertEqual(sub_value, returned_value)

    def test_retrieve_attribute_nested_value_with_operation_on_attribute(self):
        # spaces here are added on purpose at the end to make sure we
        # execute the strip in the code before the eval
        key = "key.subKey | value + 1|value / 2  |  value * 3"

        value1 = [{"d": 2}, {"g": {"h": "val"}}]
        sub_value = 1
        expected_value_after_operations = 3
        json_object = {"key": {"subKey": sub_value, "subkey2": value1}}

        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        returned_value = pollster.definitions.sample_extractor.\
            retrieve_attribute_nested_value(json_object, key)

        self.assertEqual(expected_value_after_operations, returned_value)

    def test_retrieve_attribute_nested_value_simulate_radosgw_processing(self):
        key = "user | value.split('$') | value[0] | value.strip()"

        json_object = {"categories": [
            {
                "bytes_received": 0,
                "bytes_sent": 357088,
                "category": "complete_multipart",
                "ops": 472,
                "successful_ops": 472
            }],
            "total": {
                "bytes_received": 206739531986,
                "bytes_sent": 273793180,
                "ops": 119690,
                "successful_ops": 119682
            },
            "user":
                " 00ab8d7e76fc4$00ab8d7e76fc45a37776732"
        }

        expected_value_after_operations = "00ab8d7e76fc4"

        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        returned_value = pollster.definitions.sample_extractor.\
            retrieve_attribute_nested_value(json_object, key)

        self.assertEqual(expected_value_after_operations, returned_value)

    def fake_sample_multi_metric(self, keystone_client=None, resource=None):
        multi_metric_sample_list = [
            {"categories": [
                {
                    "bytes_received": 0,
                    "bytes_sent": 0,
                    "category": "create_bucket",
                    "ops": 2,
                    "successful_ops": 2
                },
                {
                    "bytes_received": 0,
                    "bytes_sent": 2120428,
                    "category": "get_obj",
                    "ops": 46,
                    "successful_ops": 46
                },
                {
                    "bytes_received": 0,
                    "bytes_sent": 21484,
                    "category": "list_bucket",
                    "ops": 8,
                    "successful_ops": 8
                },
                {
                    "bytes_received": 6889056,
                    "bytes_sent": 0,
                    "category": "put_obj",
                    "ops": 46,
                    "successful_ops": 6
                }],
                "total": {
                    "bytes_received": 6889056,
                    "bytes_sent": 2141912,
                    "ops": 102,
                    "successful_ops": 106
                },
                "user": "test-user"}]
        return multi_metric_sample_list

    @mock.patch.object(
        dynamic_pollster.PollsterSampleGatherer,
        'execute_request_get_samples',
        fake_sample_multi_metric)
    def test_get_samples_multi_metric_pollster(self):
        pollster = dynamic_pollster.DynamicPollster(
            self.multi_metric_pollster_definition)

        fake_manager = self.FakeManager()
        samples = pollster.get_samples(
            fake_manager, None, ["https://endpoint.server.name.com/"])

        samples_list = list(samples)
        self.assertEqual(4, len(samples_list))

        create_bucket_sample = [
            s for s in samples_list
            if s.name == "test-pollster.create_bucket"][0]

        get_obj_sample = [
            s for s in samples_list
            if s.name == "test-pollster.get_obj"][0]

        list_bucket_sample = [
            s for s in samples_list
            if s.name == "test-pollster.list_bucket"][0]

        put_obj_sample = [
            s for s in samples_list
            if s.name == "test-pollster.put_obj"][0]

        self.assertEqual(2, create_bucket_sample.volume)
        self.assertEqual(46, get_obj_sample.volume)
        self.assertEqual(8, list_bucket_sample.volume)
        self.assertEqual(46, put_obj_sample.volume)
