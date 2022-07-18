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

"""Tests for Non-OpenStack dynamic pollsters
"""

import copy
import json
import sys
from unittest import mock

from oslotest import base
import requests
from urllib import parse as urlparse

from ceilometer.declarative import DynamicPollsterDefinitionException
from ceilometer.declarative import NonOpenStackApisDynamicPollsterException
from ceilometer.polling.dynamic_pollster import DynamicPollster
from ceilometer.polling.dynamic_pollster import MultiMetricPollsterDefinitions
from ceilometer.polling.dynamic_pollster import \
    NonOpenStackApisPollsterDefinition
from ceilometer.polling.dynamic_pollster import NonOpenStackApisSamplesGatherer
from ceilometer.polling.dynamic_pollster import PollsterSampleGatherer
from ceilometer.polling.dynamic_pollster import SingleMetricPollsterDefinitions


REQUIRED_POLLSTER_FIELDS = ['name', 'sample_type', 'unit', 'value_attribute',
                            'url_path', 'module', 'authentication_object']

OPTIONAL_POLLSTER_FIELDS = ['metadata_fields', 'skip_sample_values',
                            'value_mapping', 'default_value',
                            'metadata_mapping', 'preserve_mapped_metadata',
                            'response_entries_key', 'user_id_attribute',
                            'resource_id_attribute', 'barbican_secret_id',
                            'authentication_parameters',
                            'project_id_attribute']

ALL_POLLSTER_FIELDS = REQUIRED_POLLSTER_FIELDS + OPTIONAL_POLLSTER_FIELDS


def fake_sample_multi_metric(self, **kwargs):
    multi_metric_sample_list = [
        {"user_id": "UID-U007",
         "project_id": "UID-P007",
         "id": "UID-007",
         "categories": [
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


class TestNonOpenStackApisDynamicPollster(base.BaseTestCase):
    class FakeManager(object):
        _keystone = None

    class FakeResponse(object):
        status_code = None
        json_object = None

        def json(self):
            return self.json_object

        def raise_for_status(self):
            raise requests.HTTPError("Mock HTTP error.", response=self)

    def setUp(self):
        super(TestNonOpenStackApisDynamicPollster, self).setUp()
        self.pollster_definition_only_openstack_required_single_metric = {
            'name': "test-pollster", 'sample_type': "gauge", 'unit': "test",
            'value_attribute': "volume", "endpoint_type": "type",
            'url_path': "v1/test/endpoint/fake"}

        self.pollster_definition_only_openstack_required_multi_metric = {
            'name': "test-pollster.{category}", 'sample_type': "gauge",
            'unit': "test", 'value_attribute': "[categories].ops",
            'url_path': "v1/test/endpoint/fake", "endpoint_type": "type"}

        self.pollster_definition_only_required_fields = {
            'name': "test-pollster", 'sample_type': "gauge", 'unit': "test",
            'value_attribute': "volume",
            'url_path': "http://server.com/v1/test/endpoint/fake",
            'module': "module-name",
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

        self.pollster_definition_all_fields_multi_metrics = {
            'name': "test-pollster.{category}", 'sample_type': "gauge",
            'unit': "test", 'value_attribute': "[categories].ops",
            'url_path': "v1/test/endpoint/fake", 'module': "module-name",
            'authentication_object': "authentication_object",
            'user_id_attribute': 'user_id',
            'project_id_attribute': 'project_id',
            'resource_id_attribute': 'id', 'barbican_secret_id': 'barbican_id',
            'authentication_parameters': 'parameters'}

    def test_all_fields(self):
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
            self.assertIn(field, REQUIRED_POLLSTER_FIELDS)

        for field in all_optional:
            self.assertIn(field, ALL_POLLSTER_FIELDS)

    def test_all_required_fields_exceptions(self):
        for key in REQUIRED_POLLSTER_FIELDS:
            if key == 'module':
                continue
            pollster_definition = copy.deepcopy(
                self.pollster_definition_only_required_fields)
            pollster_definition.pop(key)
            exception = self.assertRaises(
                DynamicPollsterDefinitionException, DynamicPollster,
                pollster_definition, None,
                [NonOpenStackApisPollsterDefinition])
            self.assertEqual("Required fields ['%s'] not specified."
                             % key, exception.brief_message)

    def test_set_default_values(self):
        pollster = DynamicPollster(
            self.pollster_definition_only_required_fields)

        pollster_definitions = pollster.pollster_definitions

        self.assertEqual("user_id", pollster_definitions['user_id_attribute'])
        self.assertEqual("project_id",
                         pollster_definitions['project_id_attribute'])
        self.assertEqual("id", pollster_definitions['resource_id_attribute'])
        self.assertEqual('', pollster_definitions['barbican_secret_id'])
        self.assertEqual('', pollster_definitions['authentication_parameters'])

    def test_user_set_optional_parameters(self):
        pollster = DynamicPollster(
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
        pollster = DynamicPollster(
            self.pollster_definition_only_required_fields)

        self.assertEqual("barbican:", pollster.definitions.sample_gatherer.
                         default_discovery)

    def test_default_discovery_not_empty_secret_id(self):
        pollster = DynamicPollster(
            self.pollster_definition_all_fields)

        self.assertEqual("barbican:barbican_id", pollster.definitions.
                         sample_gatherer.default_discovery)

    @mock.patch('requests.get')
    def test_internal_execute_request_get_samples_status_code_ok(
            self, get_mock):
        sys.modules['module-name'] = mock.MagicMock()

        pollster = DynamicPollster(
            self.pollster_definition_only_required_fields)

        return_value = self.FakeResponse()
        return_value.status_code = requests.codes.ok
        return_value.json_object = {}
        return_value.reason = "Ok"

        get_mock.return_value = return_value

        kwargs = {'resource': "credentials"}

        resp, url = pollster.definitions.sample_gatherer.\
            _internal_execute_request_get_samples(
                pollster.definitions.configurations, **kwargs)

        self.assertEqual(
            self.pollster_definition_only_required_fields['url_path'], url)
        self.assertEqual(return_value, resp)

    @mock.patch('requests.get')
    def test_internal_execute_request_get_samples_status_code_not_ok(
            self, get_mock):
        sys.modules['module-name'] = mock.MagicMock()

        pollster = DynamicPollster(
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
                    pollster.definitions.sample_gatherer.
                    _internal_execute_request_get_samples,
                    pollster.definitions.configurations, **kwargs)

                self.assertEqual(
                    "NonOpenStackApisDynamicPollsterException"
                    " None: Error while executing request[%s]."
                    " Status[%s] and reason [%s]."
                    %
                    (self.pollster_definition_only_required_fields['url_path'],
                     http_status_code, return_value.reason), str(exception))

    def test_generate_new_attributes_in_sample_attribute_key_none(self):
        pollster = DynamicPollster(
            self.pollster_definition_only_required_fields)

        sample = {"test": "2"}
        new_key = "new-key"

        pollster.definitions.sample_gatherer. \
            generate_new_attributes_in_sample(sample, None, new_key)
        pollster.definitions.sample_gatherer. \
            generate_new_attributes_in_sample(sample, "", new_key)

        self.assertNotIn(new_key, sample)

    def test_generate_new_attributes_in_sample(self):
        pollster = DynamicPollster(
            self.pollster_definition_only_required_fields)

        sample = {"test": "2"}
        new_key = "new-key"

        pollster.definitions.sample_gatherer. \
            generate_new_attributes_in_sample(sample, "test", new_key)

        self.assertIn(new_key, sample)
        self.assertEqual(sample["test"], sample[new_key])

    def test_execute_request_get_samples_non_empty_keys(self):
        sample = {'user_id_attribute': "123456789",
                  'project_id_attribute': "dfghyt432345t",
                  'resource_id_attribute': "sdfghjt543"}

        def internal_execute_request_get_samples_mock(
                self, definitions, **kwargs):
            class Response:

                @property
                def text(self):
                    return json.dumps([sample])

                def json(self):
                    return [sample]
            return Response(), "url"

        original_method = NonOpenStackApisSamplesGatherer. \
            _internal_execute_request_get_samples
        try:
            NonOpenStackApisSamplesGatherer. \
                _internal_execute_request_get_samples = \
                internal_execute_request_get_samples_mock

            self.pollster_definition_all_fields[
                'user_id_attribute'] = 'user_id_attribute'
            self.pollster_definition_all_fields[
                'project_id_attribute'] = 'project_id_attribute'
            self.pollster_definition_all_fields[
                'resource_id_attribute'] = 'resource_id_attribute'

            pollster = DynamicPollster(
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
            NonOpenStackApisSamplesGatherer. \
                _internal_execute_request_get_samples = original_method

    def test_execute_request_get_samples_empty_keys(self):
        sample = {'user_id_attribute': "123456789",
                  'project_id_attribute': "dfghyt432345t",
                  'resource_id_attribute': "sdfghjt543"}

        def execute_request_get_samples_mock(self, **kwargs):
            samples = [sample]
            return samples

        DynamicPollster.execute_request_get_samples = \
            execute_request_get_samples_mock

        self.pollster_definition_all_fields[
            'user_id_attribute'] = None
        self.pollster_definition_all_fields[
            'project_id_attribute'] = None
        self.pollster_definition_all_fields[
            'resource_id_attribute'] = None

        pollster = DynamicPollster(
            self.pollster_definition_all_fields)

        params = {"d": "d"}
        response = pollster.execute_request_get_samples(**params)

        self.assertNotIn('user_id', response[0])
        self.assertNotIn('project_id', response[0])
        self.assertNotIn('id', response[0])

    def test_pollster_defintions_instantiation(self):
        def validate_definitions_instance(instance, isNonOpenstack,
                                          isMultiMetric, isSingleMetric):
            self.assertIs(
                isinstance(instance, NonOpenStackApisPollsterDefinition),
                isNonOpenstack)
            self.assertIs(isinstance(instance, MultiMetricPollsterDefinitions),
                          isMultiMetric)
            self.assertIs(
                isinstance(instance, SingleMetricPollsterDefinitions),
                isSingleMetric)

        pollster = DynamicPollster(
            self.pollster_definition_all_fields_multi_metrics)
        validate_definitions_instance(pollster.definitions, True, True, False)

        pollster = DynamicPollster(
            self.pollster_definition_all_fields)
        validate_definitions_instance(pollster.definitions, True, False, True)

        pollster = DynamicPollster(
            self.pollster_definition_only_openstack_required_multi_metric)
        validate_definitions_instance(pollster.definitions, False, True, False)

        pollster = DynamicPollster(
            self.pollster_definition_only_openstack_required_single_metric)
        validate_definitions_instance(pollster.definitions, False, False, True)

    @mock.patch.object(
        PollsterSampleGatherer,
        'execute_request_get_samples',
        fake_sample_multi_metric)
    def test_get_samples_multi_metric_pollster(self):
        pollster = DynamicPollster(
            self.pollster_definition_all_fields_multi_metrics)

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

    def test_get_request_linked_samples_url_no_next_sample(self):
        pollster = DynamicPollster(
            self.pollster_definition_only_required_fields)

        expected_url = self.pollster_definition_only_required_fields[
            'url_path']

        kwargs = {'resource': "non-openstack-resource"}
        url = pollster.definitions.sample_gatherer\
            .get_request_linked_samples_url(
                kwargs, pollster.definitions.configurations)

        self.assertEqual(expected_url, url)

    def test_get_request_linked_samples_url_next_sample_url(self):
        pollster = DynamicPollster(
            self.pollster_definition_only_required_fields)

        base_url = self.pollster_definition_only_required_fields['url_path']
        next_sample_path = "/next_page"
        expected_url = urlparse.urljoin(base_url, next_sample_path)

        kwargs = {'next_sample_url': expected_url}

        url = pollster.definitions.sample_gatherer\
            .get_request_linked_samples_url(kwargs, pollster.definitions)

        self.assertEqual(expected_url, url)

    def test_get_request_linked_samples_url_next_sample_only_url_path(self):
        pollster = DynamicPollster(
            self.pollster_definition_only_required_fields)

        base_url = self.pollster_definition_only_required_fields['url_path']
        next_sample_path = "/next_page"
        expected_url = urlparse.urljoin(base_url, next_sample_path)

        kwargs = {'next_sample_url': next_sample_path}

        url = pollster.definitions.sample_gatherer\
            .get_request_linked_samples_url(
                kwargs, pollster.definitions.configurations)

        self.assertEqual(expected_url, url)
