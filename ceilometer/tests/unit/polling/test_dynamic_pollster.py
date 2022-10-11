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

"""Tests for OpenStack dynamic pollster
"""
import copy
import json
import logging
from unittest import mock

import requests
from urllib import parse as urlparse

from ceilometer import declarative
from ceilometer.polling import dynamic_pollster
from ceilometer import sample
from oslotest import base

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
                self.page_link_name: [{'href': page_link, 'rel': 'next'}],
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
        _text = None

        @property
        def text(self):
            return self._text or json.dumps(self.json_object)

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
    def test_skip_samples_with_linked_samples(self, keystone_mock):
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
        pollster_definition['next_sample_url_attribute'] = \
            'server_link | filter(lambda v: v.get("rel") == "next", value) |' \
            'list(value) | value[0] | value.get("href")'
        pollster = dynamic_pollster.DynamicPollster(pollster_definition)
        samples = pollster.get_samples(fake_manager, None, ['http://test.com'])
        self.assertEqual(['ra', 'rc', 'rd', 're', 'rf', 'rg', 'rh'],
                         list(map(lambda s: s.volume, samples)))

        generator.generate_samples('http://test.com/v1/test-volumes', {
            'marker=c3': 3,
            'marker=f6': 3
        }, 2)

        pollster_definition['name'] = 'test-pollster'
        pollster_definition['value_attribute'] = 'name'
        pollster_definition['skip_sample_values'] = ['b2']
        pollster = dynamic_pollster.DynamicPollster(pollster_definition)
        samples = pollster.get_samples(fake_manager, None, ['http://test.com'])
        self.assertEqual(['a1', 'c3', 'd4', 'e5', 'f6', 'g7', 'h8'],
                         list(map(lambda s: s.volume, samples)))

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
            exception = self.assertRaises(
                declarative.DynamicPollsterDefinitionException,
                dynamic_pollster.DynamicPollster,
                pollster_definition)
            self.assertEqual("Required fields ['%s'] not specified."
                             % key, exception.brief_message)

    def test_invalid_sample_type(self):
        self.pollster_definition_only_required_fields[
            'sample_type'] = "invalid_sample_type"
        exception = self.assertRaises(
            declarative.DynamicPollsterDefinitionException,
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
    def test_execute_request_json_response_handler(
            self, client_mock):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value._text = '{"test": [1,2,3]}'

        client_mock.session.get.return_value = return_value

        samples = pollster.definitions.sample_gatherer. \
            execute_request_get_samples(
                keystone_client=client_mock,
                resource="https://endpoint.server.name/")

        self.assertEqual(3, len(samples))

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_execute_request_xml_response_handler(
            self, client_mock):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        definitions['response_handlers'] = ['xml']
        pollster = dynamic_pollster.DynamicPollster(definitions)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value._text = '<test>123</test>'
        client_mock.session.get.return_value = return_value

        samples = pollster.definitions.sample_gatherer. \
            execute_request_get_samples(
                keystone_client=client_mock,
                resource="https://endpoint.server.name/")

        self.assertEqual(3, len(samples))

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_execute_request_xml_json_response_handler(
            self, client_mock):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        definitions['response_handlers'] = ['xml', 'json']
        pollster = dynamic_pollster.DynamicPollster(definitions)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value._text = '<test>123</test>'
        client_mock.session.get.return_value = return_value

        samples = pollster.definitions.sample_gatherer. \
            execute_request_get_samples(
                keystone_client=client_mock,
                resource="https://endpoint.server.name/")

        self.assertEqual(3, len(samples))

        return_value._text = '{"test": [1,2,3,4]}'

        samples = pollster.definitions.sample_gatherer. \
            execute_request_get_samples(
                keystone_client=client_mock,
                resource="https://endpoint.server.name/")

        self.assertEqual(4, len(samples))

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_execute_request_extra_metadata_fields_cache_disabled(
            self, client_mock):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        extra_metadata_fields = {
            'extra_metadata_fields_cache_seconds': 0,
            'name': "project_name",
            'endpoint_type': "identity",
            'url_path': "'/v3/projects/' + str(sample['project_id'])",
            'value': "name",
        }
        definitions['value_attribute'] = 'project_id'
        definitions['extra_metadata_fields'] = extra_metadata_fields
        pollster = dynamic_pollster.DynamicPollster(definitions)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value._text = '''
                    {"projects": [
                        {"project_id": 9999, "name": "project1"},
                        {"project_id": 8888, "name": "project2"},
                        {"project_id": 7777, "name": "project3"},
                        {"project_id": 9999, "name": "project1"},
                        {"project_id": 8888, "name": "project2"},
                        {"project_id": 7777, "name": "project3"},
                        {"project_id": 9999, "name": "project1"},
                        {"project_id": 8888, "name": "project2"},
                        {"project_id": 7777, "name": "project3"}]
                    }
                '''

        return_value9999 = self.FakeResponse()
        return_value9999.status_code = requests.codes.ok
        return_value9999._text = '''
                    {"project":
                        {"project_id": 9999, "name": "project1"}
                    }
                '''

        return_value8888 = self.FakeResponse()
        return_value8888.status_code = requests.codes.ok
        return_value8888._text = '''
                    {"project":
                        {"project_id": 8888, "name": "project2"}
                    }
                '''

        return_value7777 = self.FakeResponse()
        return_value7777.status_code = requests.codes.ok
        return_value7777._text = '''
                    {"project":
                        {"project_id": 7777, "name": "project3"}
                    }
                '''

        def get(url, *args, **kwargs):
            if '9999' in url:
                return return_value9999
            if '8888' in url:
                return return_value8888
            if '7777' in url:
                return return_value7777
            return return_value

        client_mock.session.get.side_effect = get
        manager = mock.Mock
        manager._keystone = client_mock

        def discover(*args, **kwargs):
            return ["https://endpoint.server.name/"]

        manager.discover = discover
        samples = pollster.get_samples(
            manager=manager, cache=None,
            resources=["https://endpoint.server.name/"])

        samples = list(samples)

        n_calls = client_mock.session.get.call_count
        self.assertEqual(9, len(samples))
        self.assertEqual(10, n_calls)

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_execute_request_extra_metadata_fields_cache_enabled(
            self, client_mock):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        extra_metadata_fields = {
            'extra_metadata_fields_cache_seconds': 3600,
            'name': "project_name",
            'endpoint_type': "identity",
            'url_path': "'/v3/projects/' + str(sample['project_id'])",
            'value': "name",
        }
        definitions['value_attribute'] = 'project_id'
        definitions['extra_metadata_fields'] = extra_metadata_fields
        pollster = dynamic_pollster.DynamicPollster(definitions)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value._text = '''
                    {"projects": [
                        {"project_id": 9999, "name": "project1"},
                        {"project_id": 8888, "name": "project2"},
                        {"project_id": 7777, "name": "project3"},
                        {"project_id": 9999, "name": "project4"},
                        {"project_id": 8888, "name": "project5"},
                        {"project_id": 7777, "name": "project6"},
                        {"project_id": 9999, "name": "project7"},
                        {"project_id": 8888, "name": "project8"},
                        {"project_id": 7777, "name": "project9"}]
                    }
                '''

        return_value9999 = self.FakeResponse()
        return_value9999.status_code = requests.codes.ok
        return_value9999._text = '''
                    {"project":
                        {"project_id": 9999, "name": "project1"}
                    }
                '''

        return_value8888 = self.FakeResponse()
        return_value8888.status_code = requests.codes.ok
        return_value8888._text = '''
                    {"project":
                        {"project_id": 8888, "name": "project2"}
                    }
                '''

        return_value7777 = self.FakeResponse()
        return_value7777.status_code = requests.codes.ok
        return_value7777._text = '''
                    {"project":
                        {"project_id": 7777, "name": "project3"}
                    }
                '''

        def get(url, *args, **kwargs):
            if '9999' in url:
                return return_value9999
            if '8888' in url:
                return return_value8888
            if '7777' in url:
                return return_value7777
            return return_value

        client_mock.session.get.side_effect = get
        manager = mock.Mock
        manager._keystone = client_mock

        def discover(*args, **kwargs):
            return ["https://endpoint.server.name/"]

        manager.discover = discover
        samples = pollster.get_samples(
            manager=manager, cache=None,
            resources=["https://endpoint.server.name/"])

        samples = list(samples)

        n_calls = client_mock.session.get.call_count
        self.assertEqual(9, len(samples))
        self.assertEqual(4, n_calls)

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_execute_request_extra_metadata_fields(
            self, client_mock):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        extra_metadata_fields = [{
            'name': "project_name",
            'endpoint_type': "identity",
            'url_path': "'/v3/projects/' + str(sample['project_id'])",
            'value': "name",
            'metadata_fields': ['meta']
        }, {
            'name': "project_alias",
            'endpoint_type': "identity",
            'url_path': "'/v3/projects/' + "
                        "str(extra_metadata_captured['project_name'])",
            'value': "name",
            'metadata_fields': ['meta']
        }, {
            'name': "project_meta",
            'endpoint_type': "identity",
            'url_path': "'/v3/projects/' + "
                        "str(extra_metadata_by_name['project_name']"
                        "['metadata']['meta'])",
            'value': "project_id",
            'metadata_fields': ['meta']
        }]
        definitions['value_attribute'] = 'project_id'
        definitions['extra_metadata_fields'] = extra_metadata_fields
        pollster = dynamic_pollster.DynamicPollster(definitions)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value._text = '''
                    {"projects": [
                        {"project_id": 9999, "name": "project1"},
                        {"project_id": 8888, "name": "project2"},
                        {"project_id": 7777, "name": "project3"}]
                    }
                '''

        return_value9999 = self.FakeResponse()
        return_value9999.status_code = requests.codes.ok
        return_value9999._text = '''
                    {"project":
                        {"project_id": 9999, "name": "project1",
                        "meta": "m1"}
                    }
                '''

        return_value8888 = self.FakeResponse()
        return_value8888.status_code = requests.codes.ok
        return_value8888._text = '''
                    {"project":
                        {"project_id": 8888, "name": "project2",
                        "meta": "m2"}
                    }
                '''

        return_value7777 = self.FakeResponse()
        return_value7777.status_code = requests.codes.ok
        return_value7777._text = '''
                    {"project":
                        {"project_id": 7777, "name": "project3",
                        "meta": "m3"}
                    }
                '''

        return_valueP1 = self.FakeResponse()
        return_valueP1.status_code = requests.codes.ok
        return_valueP1._text = '''
                    {"project":
                        {"project_id": 7777, "name": "p1",
                        "meta": null}
                    }
                '''

        return_valueP2 = self.FakeResponse()
        return_valueP2.status_code = requests.codes.ok
        return_valueP2._text = '''
                    {"project":
                        {"project_id": 7777, "name": "p2",
                        "meta": null}
                    }
                '''

        return_valueP3 = self.FakeResponse()
        return_valueP3.status_code = requests.codes.ok
        return_valueP3._text = '''
                    {"project":
                        {"project_id": 7777, "name": "p3",
                        "meta": null}
                    }
                '''

        return_valueM1 = self.FakeResponse()
        return_valueM1.status_code = requests.codes.ok
        return_valueM1._text = '''
                    {"project":
                        {"project_id": "META1", "name": "p3",
                        "meta": null}
                    }
                '''

        return_valueM2 = self.FakeResponse()
        return_valueM2.status_code = requests.codes.ok
        return_valueM2._text = '''
                    {"project":
                        {"project_id": "META2", "name": "p3",
                        "meta": null}
                    }
                '''

        return_valueM3 = self.FakeResponse()
        return_valueM3.status_code = requests.codes.ok
        return_valueM3._text = '''
                    {"project":
                        {"project_id": "META3", "name": "p3",
                        "meta": null}
                    }
                '''

        def get(url, *args, **kwargs):
            if '9999' in url:
                return return_value9999
            if '8888' in url:
                return return_value8888
            if '7777' in url:
                return return_value7777
            if 'project1' in url:
                return return_valueP1
            if 'project2' in url:
                return return_valueP2
            if 'project3' in url:
                return return_valueP3
            if 'm1' in url:
                return return_valueM1
            if 'm2' in url:
                return return_valueM2
            if 'm3' in url:
                return return_valueM3

            return return_value

        client_mock.session.get = get
        manager = mock.Mock
        manager._keystone = client_mock

        def discover(*args, **kwargs):
            return ["https://endpoint.server.name/"]

        manager.discover = discover
        samples = pollster.get_samples(
            manager=manager, cache=None,
            resources=["https://endpoint.server.name/"])

        samples = list(samples)
        self.assertEqual(3, len(samples))

        self.assertEqual(samples[0].volume, 9999)
        self.assertEqual(samples[1].volume, 8888)
        self.assertEqual(samples[2].volume, 7777)

        self.assertEqual(samples[0].resource_metadata,
                         {'project_name': 'project1',
                          'project_alias': 'p1',
                          'meta': 'm1',
                          'project_meta': 'META1'})
        self.assertEqual(samples[1].resource_metadata,
                         {'project_name': 'project2',
                          'project_alias': 'p2',
                          'meta': 'm2',
                          'project_meta': 'META2'})
        self.assertEqual(samples[2].resource_metadata,
                         {'project_name': 'project3',
                          'project_alias': 'p3',
                          'meta': 'm3',
                          'project_meta': 'META3'})

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_execute_request_extra_metadata_fields_skip(
            self, client_mock):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        extra_metadata_fields = [{
            'name': "project_name",
            'endpoint_type': "identity",
            'url_path': "'/v3/projects/' + str(sample['project_id'])",
            'value': "name",
        }, {
            'name': "project_alias",
            'endpoint_type': "identity",
            'extra_metadata_fields_skip': [{
                'value': 7777
            }],
            'url_path': "'/v3/projects/' + "
                        "str(sample['p_name'])",
            'value': "name",
        }]
        definitions['value_attribute'] = 'project_id'
        definitions['metadata_fields'] = ['to_skip', 'p_name']
        definitions['extra_metadata_fields'] = extra_metadata_fields
        definitions['extra_metadata_fields_skip'] = [{
            'metadata': {
                'to_skip': 'skip1'
            }
        }, {
            'value': 8888
        }]
        pollster = dynamic_pollster.DynamicPollster(definitions)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value._text = '''
                        {"projects": [
                            {"project_id": 9999, "p_name": "project1",
                            "to_skip": "skip1"},
                            {"project_id": 8888, "p_name": "project2",
                            "to_skip": "skip2"},
                            {"project_id": 7777, "p_name": "project3",
                            "to_skip": "skip3"},
                            {"project_id": 6666, "p_name": "project4",
                            "to_skip": "skip4"}]
                        }
                    '''

        return_value9999 = self.FakeResponse()
        return_value9999.status_code = requests.codes.ok
        return_value9999._text = '''
                        {"project":
                            {"project_id": 9999, "name": "project1"}
                        }
                    '''

        return_value8888 = self.FakeResponse()
        return_value8888.status_code = requests.codes.ok
        return_value8888._text = '''
                        {"project":
                            {"project_id": 8888, "name": "project2"}
                        }
                    '''

        return_value7777 = self.FakeResponse()
        return_value7777.status_code = requests.codes.ok
        return_value7777._text = '''
                        {"project":
                            {"project_id": 7777, "name": "project3"}
                        }
                    '''

        return_value6666 = self.FakeResponse()
        return_value6666.status_code = requests.codes.ok
        return_value6666._text = '''
                        {"project":
                            {"project_id": 6666, "name": "project4"}
                        }
                    '''

        return_valueP1 = self.FakeResponse()
        return_valueP1.status_code = requests.codes.ok
        return_valueP1._text = '''
                        {"project":
                            {"project_id": 7777, "name": "p1"}
                        }
                    '''

        return_valueP2 = self.FakeResponse()
        return_valueP2.status_code = requests.codes.ok
        return_valueP2._text = '''
                        {"project":
                            {"project_id": 7777, "name": "p2"}
                        }
                    '''

        return_valueP3 = self.FakeResponse()
        return_valueP3.status_code = requests.codes.ok
        return_valueP3._text = '''
                        {"project":
                            {"project_id": 7777, "name": "p3"}
                        }
                    '''

        return_valueP4 = self.FakeResponse()
        return_valueP4.status_code = requests.codes.ok
        return_valueP4._text = '''
                        {"project":
                            {"project_id": 6666, "name": "p4"}
                        }
                    '''

        def get(url, *args, **kwargs):
            if '9999' in url:
                return return_value9999
            if '8888' in url:
                return return_value8888
            if '7777' in url:
                return return_value7777
            if '6666' in url:
                return return_value6666
            if 'project1' in url:
                return return_valueP1
            if 'project2' in url:
                return return_valueP2
            if 'project3' in url:
                return return_valueP3
            if 'project4' in url:
                return return_valueP4

            return return_value

        client_mock.session.get = get
        manager = mock.Mock
        manager._keystone = client_mock

        def discover(*args, **kwargs):
            return ["https://endpoint.server.name/"]

        manager.discover = discover
        samples = pollster.get_samples(
            manager=manager, cache=None,
            resources=["https://endpoint.server.name/"])

        samples = list(samples)
        self.assertEqual(4, len(samples))

        self.assertEqual(samples[0].volume, 9999)
        self.assertEqual(samples[1].volume, 8888)
        self.assertEqual(samples[2].volume, 7777)

        self.assertEqual(samples[0].resource_metadata,
                         {'p_name': 'project1', 'project_alias': 'p1',
                          'to_skip': 'skip1'})
        self.assertEqual(samples[1].resource_metadata,
                         {'p_name': 'project2', 'project_alias': 'p2',
                          'to_skip': 'skip2'})
        self.assertEqual(samples[2].resource_metadata,
                         {'p_name': 'project3', 'project_name': 'project3',
                          'to_skip': 'skip3'})
        self.assertEqual(samples[3].resource_metadata,
                         {'p_name': 'project4',
                          'project_alias': 'p4',
                          'project_name': 'project4',
                          'to_skip': 'skip4'})

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_execute_request_extra_metadata_fields_different_requests(
            self, client_mock):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)

        command = ''' \'\'\'echo '{"project":
        {"project_id": \'\'\'+ str(sample['project_id'])
         +\'\'\' , "name": "project1"}}' \'\'\' '''.replace('\n', '')

        command2 = ''' \'\'\'echo '{"project":
        {"project_id": \'\'\'+ str(sample['project_id'])
         +\'\'\' , "name": "project2"}}' \'\'\' '''.replace('\n', '')

        extra_metadata_fields_embedded = {
            'name': "project_name2",
            'host_command': command2,
            'value': "name",
        }

        extra_metadata_fields = {
            'name': "project_id2",
            'host_command': command,
            'value': "project_id",
            'extra_metadata_fields': extra_metadata_fields_embedded
        }

        definitions['value_attribute'] = 'project_id'
        definitions['extra_metadata_fields'] = extra_metadata_fields
        pollster = dynamic_pollster.DynamicPollster(definitions)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value._text = '''
                    {"projects": [
                        {"project_id": 9999, "name": "project1"},
                        {"project_id": 8888, "name": "project2"},
                        {"project_id": 7777, "name": "project3"}]
                    }
                '''

        def get(url, *args, **kwargs):
            return return_value

        client_mock.session.get = get
        manager = mock.Mock
        manager._keystone = client_mock

        def discover(*args, **kwargs):
            return ["https://endpoint.server.name/"]

        manager.discover = discover
        samples = pollster.get_samples(
            manager=manager, cache=None,
            resources=["https://endpoint.server.name/"])

        samples = list(samples)
        self.assertEqual(3, len(samples))

        self.assertEqual(samples[0].volume, 9999)
        self.assertEqual(samples[1].volume, 8888)
        self.assertEqual(samples[2].volume, 7777)

        self.assertEqual(samples[0].resource_metadata,
                         {'project_id2': 9999,
                          'project_name2': 'project2'})
        self.assertEqual(samples[1].resource_metadata,
                         {'project_id2': 8888,
                          'project_name2': 'project2'})
        self.assertEqual(samples[2].resource_metadata,
                         {'project_id2': 7777,
                          'project_name2': 'project2'})

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_execute_request_xml_json_response_handler_invalid_response(
            self, client_mock):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        definitions['response_handlers'] = ['xml', 'json']
        pollster = dynamic_pollster.DynamicPollster(definitions)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value._text = 'Invalid response'
        client_mock.session.get.return_value = return_value

        with self.assertLogs('ceilometer.polling.dynamic_pollster',
                             level='DEBUG') as logs:
            gatherer = pollster.definitions.sample_gatherer
            exception = self.assertRaises(
                declarative.InvalidResponseTypeException,
                gatherer.execute_request_get_samples,
                keystone_client=client_mock,
                resource="https://endpoint.server.name/")

            xml_handling_error = logs.output[3]
            json_handling_error = logs.output[4]

            self.assertIn(
                'DEBUG:ceilometer.polling.dynamic_pollster:'
                'Error handling response [Invalid response] '
                'with handler [XMLResponseHandler]',
                xml_handling_error)

            self.assertIn(
                'DEBUG:ceilometer.polling.dynamic_pollster:'
                'Error handling response [Invalid response] '
                'with handler [JsonResponseHandler]',
                json_handling_error)

            self.assertEqual(
                "InvalidResponseTypeException None: "
                "No remaining handlers to handle the response "
                "[Invalid response], used handlers "
                "[XMLResponseHandler, JsonResponseHandler]. "
                "[{'url_path': 'v1/test/endpoint/fake'}].",
                str(exception))

    def test_configure_response_handler_definition_invalid_value(self):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        definitions['response_handlers'] = ['jason']

        exception = self.assertRaises(
            declarative.DynamicPollsterDefinitionException,
            dynamic_pollster.DynamicPollster,
            pollster_definitions=definitions)
        self.assertEqual("DynamicPollsterDefinitionException None: "
                         "Invalid response_handler value [jason]. "
                         "Accepted values are [json, xml, text]",
                         str(exception))

    def test_configure_extra_metadata_field_skip_invalid_value(self):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        definitions['extra_metadata_fields_skip'] = 'teste'

        exception = self.assertRaises(
            declarative.DynamicPollsterDefinitionException,
            dynamic_pollster.DynamicPollster,
            pollster_definitions=definitions)
        self.assertEqual("DynamicPollsterDefinitionException None: "
                         "Invalid extra_metadata_fields_skip configuration."
                         " It must be a list of maps. Provided value: teste,"
                         " value type: str.",
                         str(exception))

    def test_configure_extra_metadata_field_skip_invalid_sub_value(self):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        definitions['extra_metadata_fields_skip'] = [{'test': '1'},
                                                     {'test': '2'},
                                                     'teste']

        exception = self.assertRaises(
            declarative.DynamicPollsterDefinitionException,
            dynamic_pollster.DynamicPollster,
            pollster_definitions=definitions)
        self.assertEqual("DynamicPollsterDefinitionException None: "
                         "Invalid extra_metadata_fields_skip configuration."
                         " It must be a list of maps. Provided value: "
                         "[{'test': '1'}, {'test': '2'}, 'teste'], "
                         "value type: list.",
                         str(exception))

    def test_configure_response_handler_definition_invalid_type(self):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        definitions['response_handlers'] = 'json'

        exception = self.assertRaises(
            declarative.DynamicPollsterDefinitionException,
            dynamic_pollster.DynamicPollster,
            pollster_definitions=definitions)
        self.assertEqual("DynamicPollsterDefinitionException None: "
                         "Invalid response_handlers configuration. "
                         "It must be a list. Provided value type: str",
                         str(exception))

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

    def test_execute_host_command_paged_responses(self):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        definitions['host_command'] = '''
        echo '{"server": [{"status": "ACTIVE"}], "next": ""}'
        '''
        str_json = "'{\\\"server\\\": [{\\\"status\\\": \\\"INACTIVE\\\"}]}'"
        definitions['next_sample_url_attribute'] = \
            "next|\"echo \"+value+\"" + str_json + '"'
        pollster = dynamic_pollster.DynamicPollster(definitions)
        samples = pollster.definitions.sample_gatherer. \
            execute_request_get_samples()
        resp_json = [{'status': 'ACTIVE'}, {'status': 'INACTIVE'}]
        self.assertEqual(resp_json, samples)

    def test_execute_host_command_response_handler(self):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        definitions['response_handlers'] = ['xml', 'json']
        definitions['host_command'] = 'echo "<a><y>xml\n</y><s>xml</s></a>"'
        entry = 'a'
        definitions['response_entries_key'] = entry
        definitions.pop('url_path')
        definitions.pop('endpoint_type')
        pollster = dynamic_pollster.DynamicPollster(definitions)

        samples_xml = pollster.definitions.sample_gatherer. \
            execute_request_get_samples()

        definitions['host_command'] = 'echo \'{"a": {"y":"json",' \
                                      '\n"s":"json"}}\''
        samples_json = pollster.definitions.sample_gatherer. \
            execute_request_get_samples()

        resp_xml = {'a': {'y': 'xml', 's': 'xml'}}
        resp_json = {'a': {'y': 'json', 's': 'json'}}
        self.assertEqual(resp_xml[entry], samples_xml)
        self.assertEqual(resp_json[entry], samples_json)

    def test_execute_host_command_invalid_command(self):
        definitions = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        definitions['host_command'] = 'invalid-command'
        definitions.pop('url_path')
        definitions.pop('endpoint_type')
        pollster = dynamic_pollster.DynamicPollster(definitions)

        self.assertRaises(
            declarative.InvalidResponseTypeException,
            pollster.definitions.sample_gatherer.execute_request_get_samples)

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

    def fake_sample_list(self, **kwargs):
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
            retrieve_entries_from_response(response, pollster.definitions)

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
        entries = pollster.definitions.sample_gatherer.\
            retrieve_entries_from_response(
                response, pollster.definitions.configurations)

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
            retrieve_entries_from_response(response,
                                           pollster.definitions.configurations)

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

    def fake_sample_multi_metric(self, **kwargs):
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

    def test_execute_request_get_samples_custom_ids(self):
        sample = {'user_id_attribute': "1",
                  'project_id_attribute': "2",
                  'resource_id_attribute': "3",
                  'user_id': "234",
                  'project_id': "2334",
                  'id': "35"}

        def internal_execute_request_get_samples_mock(self, **kwargs):
            class Response:
                @property
                def text(self):
                    return json.dumps([sample])

                def json(self):
                    return [sample]
            return Response(), "url"

        original_method = dynamic_pollster.PollsterSampleGatherer.\
            _internal_execute_request_get_samples
        try:
            dynamic_pollster.PollsterSampleGatherer. \
                _internal_execute_request_get_samples = \
                internal_execute_request_get_samples_mock

            self.pollster_definition_all_fields[
                'user_id_attribute'] = 'user_id_attribute'
            self.pollster_definition_all_fields[
                'project_id_attribute'] = 'project_id_attribute'
            self.pollster_definition_all_fields[
                'resource_id_attribute'] = 'resource_id_attribute'

            pollster = dynamic_pollster.DynamicPollster(
                self.pollster_definition_all_fields)

            params = {"d": "d"}
            response = pollster.definitions.sample_gatherer. \
                execute_request_get_samples(**params)

            self.assertEqual(sample['user_id_attribute'],
                             response[0]['user_id'])
            self.assertEqual(sample['project_id_attribute'],
                             response[0]['project_id'])
            self.assertEqual(sample['resource_id_attribute'],
                             response[0]['id'])
        finally:
            dynamic_pollster.PollsterSampleGatherer. \
                _internal_execute_request_get_samples = original_method

    def test_retrieve_attribute_self_reference_sample(self):
        key = " . | value['key1']['subKey1'][0]['d'] if 'key1' in value else 0"

        sub_value1 = [{"d": 2}, {"g": {"h": "val"}}]
        sub_value2 = [{"r": 245}, {"h": {"yu": "yu"}}]

        json_object = {"key1": {"subKey1": sub_value1},
                       "key2": {"subkey2": sub_value2}}

        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        returned_value = pollster.definitions.sample_extractor.\
            retrieve_attribute_nested_value(json_object, key)
        self.assertEqual(2, returned_value)

        del json_object['key1']
        returned_value = pollster.definitions.sample_extractor.\
            retrieve_attribute_nested_value(json_object, key)
        self.assertEqual(0, returned_value)

    def test_create_request_arguments_NonOpenStackApisSamplesGatherer(self):
        pollster_definition = {
            'name': "test-pollster", 'sample_type': "gauge", 'unit': "test",
            'value_attribute': "volume",
            'url_path': "https://test.com/v1/test/endpoint/fake",
            "module": "someModule",
            "authentication_object": "objectAuthentication",
            "authentication_parameters": "authParam",
            "headers": [{"header1": "val1"}, {"header2": "val2"}]}

        pollster = dynamic_pollster.DynamicPollster(pollster_definition)

        request_args = pollster.definitions.sample_gatherer\
            .create_request_arguments(pollster.definitions.configurations)

        self.assertTrue("headers" in request_args)
        self.assertEqual(2, len(request_args["headers"]))

        self.assertEqual(['header1', 'header2'],
                         list(map(lambda h: list(h.keys())[0],
                                  request_args["headers"])))

        self.assertEqual(['val1', 'val2'],
                         list(map(lambda h: list(h.values())[0],
                                  request_args["headers"])))

        self.assertTrue("authenticated" not in request_args)

    def test_create_request_arguments_PollsterSampleGatherer(self):
        pollster_definition = copy.deepcopy(
            self.pollster_definition_only_required_fields)
        pollster_definition["headers"] = [
            {"x-openstack-nova-api-version": "2.46"},
            {"custom_header": "custom"},
            {"some_other_header": "something"}]

        pollster = dynamic_pollster.DynamicPollster(pollster_definition)

        request_args = pollster.definitions.sample_gatherer\
            .create_request_arguments(pollster.definitions.configurations)

        self.assertTrue("headers" in request_args)
        self.assertTrue("authenticated" in request_args)
        self.assertTrue(request_args["authenticated"])

        self.assertEqual(3, len(request_args["headers"]))

        self.assertEqual(['x-openstack-nova-api-version', 'custom_header',
                          "some_other_header"],
                         list(map(lambda h: list(h.keys())[0],
                                  request_args["headers"])))

        self.assertEqual(['2.46', 'custom', 'something'],
                         list(map(lambda h: list(h.values())[0],
                                  request_args["headers"])))

    def test_create_request_arguments_PollsterSampleGatherer_no_headers(self):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        request_args =\
            pollster.definitions.sample_gatherer.create_request_arguments(
                pollster.definitions.configurations)

        self.assertTrue("headers" not in request_args)
        self.assertTrue("authenticated" in request_args)
        self.assertTrue(request_args["authenticated"])

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_metadata_nested_objects(self, keystone_mock):
        generator = PagedSamplesGeneratorHttpRequestMock(samples_dict={
            'flavor': [{"name": "a", "ram": 1}, {"name": "b", "ram": 2},
                       {"name": "c", "ram": 3}, {"name": "d", "ram": 4},
                       {"name": "e", "ram": 5}, {"name": "f", "ram": 6},
                       {"name": "g", "ram": 7}, {"name": "h", "ram": 8}],
            'name': ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8'],
            'state': ['Active', 'Error', 'Down', 'Active', 'Active',
                      'Migrating', 'Active', 'Error']
        }, dict_name='servers', page_link_name='server_link')

        generator.generate_samples('http://test.com/v1/test-servers', {
            'marker=c3': 3,
            'marker=f6': 3
        }, 2)

        keystone_mock.session.get.side_effect = generator.mock_request
        fake_manager = self.FakeManager(keystone=keystone_mock)

        pollster_definition = dict(self.multi_metric_pollster_definition)
        pollster_definition['name'] = 'test-pollster'
        pollster_definition['value_attribute'] = 'state'
        pollster_definition['url_path'] = 'v1/test-servers'
        pollster_definition['response_entries_key'] = 'servers'
        pollster_definition['metadata_fields'] = ['flavor.name', 'flavor.ram']
        pollster_definition['next_sample_url_attribute'] = \
            'server_link | filter(lambda v: v.get("rel") == "next", value) |' \
            'list(value)| value [0] | value.get("href")'
        pollster = dynamic_pollster.DynamicPollster(pollster_definition)

        samples = pollster.get_samples(fake_manager, None, ['http://test.com'])

        samples = list(samples)

        self.assertEqual(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
                         list(map(lambda s: s.resource_metadata["flavor.name"],
                                  samples)))
        self.assertEqual(list(range(1, 9)),
                         list(map(lambda s: s.resource_metadata["flavor.ram"],
                                  samples)))

    def test_get_request_linked_samples_url_no_next_sample(self):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        base_url = "http://test.com/something_that_we_do_not_care"
        expected_url = urlparse.urljoin(
            base_url, self.pollster_definition_only_required_fields[
                'url_path'])

        kwargs = {'resource': base_url}
        url = pollster.definitions.sample_gatherer\
            .get_request_linked_samples_url(
                kwargs, pollster.definitions.configurations)

        self.assertEqual(expected_url, url)

    def test_get_request_linked_samples_url_next_sample_url(self):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        base_url = "http://test.com/something_that_we_do_not_care"
        expected_url = "http://test.com/next_page"

        kwargs = {'resource': base_url,
                  'next_sample_url': expected_url}

        url = pollster.definitions.sample_gatherer\
            .get_request_linked_samples_url(kwargs, pollster.definitions)

        self.assertEqual(expected_url, url)

    def test_get_request_linked_samples_url_next_sample_only_url_path(self):
        pollster = dynamic_pollster.DynamicPollster(
            self.pollster_definition_only_required_fields)

        base_url = "http://test.com/something_that_we_do_not_care"
        expected_url = "http://test.com/next_page"

        kwargs = {'resource': base_url,
                  'next_sample_url': "/next_page"}

        url = pollster.definitions.sample_gatherer\
            .get_request_linked_samples_url(
                kwargs, pollster.definitions.configurations)

        self.assertEqual(expected_url, url)

    def test_generate_sample_and_extract_metadata(self):
        definition = self.pollster_definition_only_required_fields.copy()
        definition['metadata_fields'] = ["metadata1", 'metadata2']

        pollster = dynamic_pollster.DynamicPollster(definition)

        pollster_sample = {'metadata1': 'metadata1',
                           'metadata2': 'metadata2',
                           'value': 1}

        sample = pollster.definitions.sample_extractor.generate_sample(
            pollster_sample, pollster.definitions.configurations,
            manager=mock.Mock(), conf={})

        self.assertEqual(1, sample.volume)
        self.assertEqual(2, len(sample.resource_metadata))
        self.assertEqual('metadata1', sample.resource_metadata['metadata1'])
        self.assertEqual('metadata2', sample.resource_metadata['metadata2'])

    def test_generate_sample_and_extract_metadata_false_value(self):
        definition = self.pollster_definition_only_required_fields.copy()
        definition['metadata_fields'] = ["metadata1",
                                         'metadata2',
                                         'metadata3_false']

        pollster = dynamic_pollster.DynamicPollster(definition)

        pollster_sample = {'metadata1': 'metadata1',
                           'metadata2': 'metadata2',
                           'metadata3_false': False,
                           'value': 1}

        sample = pollster.definitions.sample_extractor.generate_sample(
            pollster_sample, pollster.definitions.configurations,
            manager=mock.Mock(), conf={})

        self.assertEqual(1, sample.volume)
        self.assertEqual(3, len(sample.resource_metadata))
        self.assertEqual('metadata1', sample.resource_metadata['metadata1'])
        self.assertEqual('metadata2', sample.resource_metadata['metadata2'])
        self.assertIs(False, sample.resource_metadata['metadata3_false'])

    def test_generate_sample_and_extract_metadata_none_value(self):
        definition = self.pollster_definition_only_required_fields.copy()
        definition['metadata_fields'] = ["metadata1",
                                         'metadata2',
                                         'metadata3']

        pollster = dynamic_pollster.DynamicPollster(definition)

        pollster_sample = {'metadata1': 'metadata1',
                           'metadata2': 'metadata2',
                           'metadata3': None,
                           'value': 1}

        sample = pollster.definitions.sample_extractor.generate_sample(
            pollster_sample, pollster.definitions.configurations,
            manager=mock.Mock(), conf={})

        self.assertEqual(1, sample.volume)
        self.assertEqual(3, len(sample.resource_metadata))
        self.assertEqual('metadata1', sample.resource_metadata['metadata1'])
        self.assertEqual('metadata2', sample.resource_metadata['metadata2'])
        self.assertIsNone(sample.resource_metadata['metadata3'])
