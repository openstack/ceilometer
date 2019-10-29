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

"""Dynamic pollster component
    This component enables operators to create new pollsters on the fly
    via configuration. The configuration files are read from
    '/etc/ceilometer/pollsters.d/'. The pollster are defined in YAML files
    similar to the idea used for handling notifications.
"""
from oslo_log import log
from oslo_utils import timeutils

from requests import RequestException

from ceilometer import declarative
from ceilometer.polling import plugin_base
from ceilometer import sample

from functools import reduce
import operator
import requests

from six.moves.urllib import parse as url_parse

LOG = log.getLogger(__name__)


class DynamicPollster(plugin_base.PollsterBase):

    OPTIONAL_POLLSTER_FIELDS = ['metadata_fields', 'skip_sample_values',
                                'value_mapping', 'default_value',
                                'metadata_mapping',
                                'preserve_mapped_metadata'
                                'response_entries_key']

    REQUIRED_POLLSTER_FIELDS = ['name', 'sample_type', 'unit',
                                'value_attribute', 'endpoint_type',
                                'url_path']

    ALL_POLLSTER_FIELDS = OPTIONAL_POLLSTER_FIELDS + REQUIRED_POLLSTER_FIELDS

    name = ""

    def __init__(self, pollster_definitions, conf=None):
        super(DynamicPollster, self).__init__(conf)
        LOG.debug("Dynamic pollster created with [%s]",
                  pollster_definitions)

        self.pollster_definitions = pollster_definitions
        self.validate_pollster_definition()

        if 'metadata_fields' in self.pollster_definitions:
            LOG.debug("Metadata fields configured to [%s].",
                      self.pollster_definitions['metadata_fields'])

        self.name = self.pollster_definitions['name']
        self.obj = self

        if 'skip_sample_values' not in self.pollster_definitions:
            self.pollster_definitions['skip_sample_values'] = []

        if 'value_mapping' not in self.pollster_definitions:
            self.pollster_definitions['value_mapping'] = {}

        if 'default_value' not in self.pollster_definitions:
            self.pollster_definitions['default_value'] = -1

        if 'preserve_mapped_metadata' not in self.pollster_definitions:
            self.pollster_definitions['preserve_mapped_metadata'] = True

        if 'metadata_mapping' not in self.pollster_definitions:
            self.pollster_definitions['metadata_mapping'] = {}

        if 'response_entries_key' not in self.pollster_definitions:
            self.pollster_definitions['response_entries_key'] = None

    def validate_pollster_definition(self):
        missing_required_fields = \
            [field for field in self.REQUIRED_POLLSTER_FIELDS
             if field not in self.pollster_definitions]

        if missing_required_fields:
            raise declarative.DynamicPollsterDefinitionException(
                "Required fields %s not specified."
                % missing_required_fields, self.pollster_definitions)

        sample_type = self.pollster_definitions['sample_type']
        if sample_type not in sample.TYPES:
            raise declarative.DynamicPollsterDefinitionException(
                "Invalid sample type [%s]. Valid ones are [%s]."
                % (sample_type, sample.TYPES), self.pollster_definitions)

        for definition_key in self.pollster_definitions:
            if definition_key not in self.ALL_POLLSTER_FIELDS:
                LOG.warning(
                    "Field [%s] defined in [%s] is unknown "
                    "and will be ignored. Valid fields are [%s].",
                    definition_key, self.pollster_definitions,
                    self.ALL_POLLSTER_FIELDS)

    def get_samples(self, manager, cache, resources):
        if not resources:
            LOG.debug("No resources received for processing.")
            yield None

        for endpoint in resources:
            LOG.debug("Executing get sample on URL [%s].", endpoint)

            samples = list([])
            try:
                samples = self.execute_request_get_samples(
                    keystone_client=manager._keystone, endpoint=endpoint)
            except RequestException as e:
                LOG.warning("Error [%s] while loading samples for [%s] "
                            "for dynamic pollster [%s].",
                            e, endpoint, self.name)

            for pollster_sample in samples:
                response_value_attribute_name = self.pollster_definitions[
                    'value_attribute']
                value = self.retrieve_attribute_nested_value(
                    pollster_sample, response_value_attribute_name)

                skip_sample_values = \
                    self.pollster_definitions['skip_sample_values']
                if skip_sample_values and value in skip_sample_values:
                    LOG.debug("Skipping sample [%s] because value [%s] "
                              "is configured to be skipped in skip list [%s].",
                              pollster_sample, value, skip_sample_values)
                    continue

                value = self.execute_value_mapping(value)

                user_id = None
                if 'user_id' in pollster_sample:
                    user_id = pollster_sample["user_id"]

                project_id = None
                if 'project_id' in pollster_sample:
                    project_id = pollster_sample["project_id"]

                metadata = []
                if 'metadata_fields' in self.pollster_definitions:
                    metadata = dict((k, pollster_sample.get(k))
                                    for k in self.pollster_definitions[
                                        'metadata_fields'])
                self.generate_new_metadata_fields(metadata=metadata)
                yield sample.Sample(
                    timestamp=timeutils.isotime(),

                    name=self.pollster_definitions['name'],
                    type=self.pollster_definitions['sample_type'],
                    unit=self.pollster_definitions['unit'],
                    volume=value,

                    user_id=user_id,
                    project_id=project_id,
                    resource_id=pollster_sample["id"],

                    resource_metadata=metadata
                )

    def execute_value_mapping(self, value):
        value_mapping = self.pollster_definitions['value_mapping']
        if value_mapping:
            if value in value_mapping:
                old_value = value
                value = value_mapping[value]
                LOG.debug("Value mapped from [%s] to [%s]",
                          old_value, value)
            else:
                default_value = \
                    self.pollster_definitions['default_value']
                LOG.warning(
                    "Value [%s] was not found in value_mapping [%s]; "
                    "therefore, we will use the default [%s].",
                    value, value_mapping, default_value)
                value = default_value
        return value

    def generate_new_metadata_fields(self, metadata=None):
        metadata_mapping = self.pollster_definitions['metadata_mapping']
        if not metadata_mapping or not metadata:
            return

        metadata_keys = list(metadata.keys())
        for k in metadata_keys:
            if k not in metadata_mapping:
                continue

            new_key = metadata_mapping[k]
            metadata[new_key] = metadata[k]
            LOG.debug("Generating new key [%s] with content [%s] of key [%s]",
                      new_key, metadata[k], k)
            if self.pollster_definitions['preserve_mapped_metadata']:
                continue

            k_value = metadata.pop(k)
            LOG.debug("Removed key [%s] with value [%s] from "
                      "metadata set that is sent to Gnocchi.", k, k_value)

    @property
    def default_discovery(self):
        return 'endpoint:' + self.pollster_definitions['endpoint_type']

    def execute_request_get_samples(self, keystone_client, endpoint):
        url = url_parse.urljoin(
            endpoint, self.pollster_definitions['url_path'])
        resp = keystone_client.session.get(url, authenticated=True)
        if resp.status_code != requests.codes.ok:
            resp.raise_for_status()

        response_json = resp.json()

        entry_size = len(response_json)
        LOG.debug("Entries [%s] in the JSON for request [%s] "
                  "for dynamic pollster [%s].",
                  response_json, url, self.name)

        if entry_size > 0:
            return self.retrieve_entries_from_response(response_json)
        return []

    def retrieve_entries_from_response(self, response_json):
        if isinstance(response_json, list):
            return response_json

        first_entry_name = self.pollster_definitions['response_entries_key']
        if not first_entry_name:
            try:
                first_entry_name = next(iter(response_json))
            except RuntimeError as e:
                LOG.debug("Generator threw a StopIteration "
                          "and we need to catch it [%s].", e)
        return self.retrieve_attribute_nested_value(response_json,
                                                    first_entry_name)

    def retrieve_attribute_nested_value(self, json_object, attribute_key):
        LOG.debug("Retrieving the nested keys [%s] from [%s].",
                  attribute_key, json_object)
        nested_keys = attribute_key.split(".")
        return reduce(operator.getitem, nested_keys, json_object)
