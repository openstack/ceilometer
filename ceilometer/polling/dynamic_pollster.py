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
import copy
import re

from oslo_log import log
from oslo_utils import timeutils

from requests import RequestException

from ceilometer import declarative
from ceilometer.polling import plugin_base
from ceilometer import sample as ceilometer_sample

from functools import reduce
import operator
import requests

from six.moves.urllib import parse as url_parse

LOG = log.getLogger(__name__)


def validate_sample_type(sample_type):
    if sample_type not in ceilometer_sample.TYPES:
        raise declarative.DynamicPollsterDefinitionException(
            "Invalid sample type [%s]. Valid ones are [%s]."
            % (sample_type, ceilometer_sample.TYPES))


class PollsterDefinitionBuilder(object):

    def __init__(self, definitions):
        self.definitions = definitions

    def build_definitions(self, configurations):
        supported_definitions = []
        for definition in self.definitions:
            if definition.is_field_applicable_to_definition(configurations):
                supported_definitions.append(definition)

        if not supported_definitions:
            raise declarative.DynamicPollsterDefinitionException(
                "Your configurations do not fit any type of DynamicPollsters, "
                "please recheck them. Used configurations are [%s]." %
                configurations)

        definition_name = self.join_supported_definitions_names(
            supported_definitions)

        definition_parents = tuple(supported_definitions)
        definition_attribs = {'extra_definitions': reduce(
            lambda d1, d2: d1 + d2, map(lambda df: df.extra_definitions,
                                        supported_definitions))}
        definition_type = type(definition_name, definition_parents,
                               definition_attribs)
        return definition_type(configurations)

    @staticmethod
    def join_supported_definitions_names(supported_definitions):
        return ''.join(map(lambda df: df.__name__,
                           supported_definitions))


class PollsterSampleExtractor(object):

    def __init__(self, definitions):
        self.definitions = definitions

    def generate_new_metadata_fields(self, metadata=None,
                                     pollster_definitions=None):
        pollster_definitions =\
            pollster_definitions or self.definitions.configurations
        metadata_mapping = pollster_definitions['metadata_mapping']
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
            if pollster_definitions['preserve_mapped_metadata']:
                continue

            k_value = metadata.pop(k)
            LOG.debug("Removed key [%s] with value [%s] from "
                      "metadata set that is sent to Gnocchi.", k, k_value)

    def generate_sample(self, pollster_sample, pollster_definitons=None):
        pollster_definitions =\
            pollster_definitons or self.definitions.configurations

        metadata = dict()
        if 'metadata_fields' in pollster_definitions:
            for k in pollster_definitions['metadata_fields']:
                val = self.retrieve_attribute_nested_value(pollster_sample, k)

                LOG.debug("Assigning value [%s] to metadata key [%s].", val, k)
                metadata[k] = val

        self.generate_new_metadata_fields(
            metadata=metadata, pollster_definitions=pollster_definitions)
        return ceilometer_sample.Sample(
            timestamp=timeutils.isotime(),
            name=pollster_definitions['name'],
            type=pollster_definitions['sample_type'],
            unit=pollster_definitions['unit'],
            volume=pollster_sample['value'],
            user_id=pollster_sample.get("user_id"),
            project_id=pollster_sample.get("project_id"),
            resource_id=pollster_sample.get("id"),
            resource_metadata=metadata)

    def retrieve_attribute_nested_value(self, json_object,
                                        value_attribute=None):

        attribute_key = value_attribute or self.definitions.\
            extract_attribute_key()

        LOG.debug(
            "Retrieving the nested keys [%s] from [%s] or pollster [""%s].",
            attribute_key, json_object,
            self.definitions.configurations["name"])

        keys_and_operations = attribute_key.split("|")
        attribute_key = keys_and_operations[0].strip()

        if attribute_key == ".":
            value = json_object
        else:
            nested_keys = attribute_key.split(".")
            value = reduce(operator.getitem, nested_keys, json_object)

        return self.operate_value(keys_and_operations, value)

    def operate_value(self, keys_and_operations, value):
        # We do not have operations to be executed against the value extracted
        if len(keys_and_operations) < 2:
            return value
        for operation in keys_and_operations[1::]:
            # The operation must be performed onto the 'value' variable
            if 'value' not in operation:
                raise declarative.DynamicPollsterDefinitionException(
                    "The attribute field operation [%s] must use the ["
                    "value] variable." % operation,
                    self.definitions.configurations)

            LOG.debug("Executing operation [%s] against value[%s] for "
                      "pollster [%s].", operation, value,
                      self.definitions.configurations["name"])

            value = eval(operation.strip())
            LOG.debug(
                "Result [%s] of operation [%s] for pollster [%s].",
                value, operation, self.definitions.configurations["name"])
        return value


class SimplePollsterSampleExtractor(PollsterSampleExtractor):

    def generate_single_sample(self, pollster_sample):
        value = self.retrieve_attribute_nested_value(pollster_sample)
        value = self.definitions.value_mapper.map_or_skip_value(
            value, pollster_sample)

        if isinstance(value, SkippedSample):
            return value

        pollster_sample['value'] = value

        return self.generate_sample(pollster_sample)

    def extract_sample(self, pollster_sample):
        sample = self.generate_single_sample(pollster_sample)
        if isinstance(sample, SkippedSample):
            return sample
        yield sample


class MultiMetricPollsterSampleExtractor(PollsterSampleExtractor):

    def extract_sample(self, pollster_sample):
        pollster_definitions = self.definitions.configurations
        value = self.retrieve_attribute_nested_value(pollster_sample)
        LOG.debug("We are dealing with a multi metric pollster. The "
                  "value we are processing is the following: [%s].",
                  value)

        self.validate_sample_is_list(value)
        sub_metric_placeholder, pollster_name, sub_metric_attribute_name = \
            self.extract_names_attrs()

        value_attribute = \
            self.extract_field_name_from_value_attribute_configuration()
        LOG.debug("Using attribute [%s] to look for values in the "
                  "multi metric pollster [%s] with sample [%s]",
                  value_attribute, pollster_definitions, value)

        pollster_definitions = copy.deepcopy(pollster_definitions)
        yield from self.extract_sub_samples(value, sub_metric_attribute_name,
                                            pollster_name, value_attribute,
                                            sub_metric_placeholder,
                                            pollster_definitions,
                                            pollster_sample)

    def extract_sub_samples(self, value, sub_metric_attribute_name,
                            pollster_name, value_attribute,
                            sub_metric_placeholder, pollster_definitions,
                            pollster_sample):

        for sub_sample in value:
            sub_metric_name = sub_sample[sub_metric_attribute_name]
            new_metric_name = pollster_name.replace(
                sub_metric_placeholder, sub_metric_name)
            pollster_definitions['name'] = new_metric_name

            actual_value = self.retrieve_attribute_nested_value(
                sub_sample, value_attribute)

            pollster_sample['value'] = actual_value

            if self.should_skip_generate_sample(actual_value, sub_sample,
                                                sub_metric_name):
                continue

            yield self.generate_sample(pollster_sample, pollster_definitions)

    def extract_field_name_from_value_attribute_configuration(self):
        value_attribute = self.definitions.configurations['value_attribute']
        return self.definitions.pattern_pollster_value_attribute.match(
            value_attribute).group(3)[1::]

    def extract_names_attrs(self):
        pollster_name = self.definitions.configurations['name']
        sub_metric_placeholder = pollster_name.split(".").pop()
        return (sub_metric_placeholder,
                pollster_name,
                self.definitions.pattern_pollster_name.match(
                    "." + sub_metric_placeholder).group(2))

    def validate_sample_is_list(self, value):
        pollster_definitions = self.definitions.configurations
        if not isinstance(value, list):
            raise declarative.DynamicPollsterException(
                "Multi metric pollster defined, but the value [%s]"
                " obtained with [%s] attribute is not a list"
                " of objects."
                % (value,
                   pollster_definitions['value_attribute']),
                pollster_definitions)

    def should_skip_generate_sample(self, actual_value, sub_sample,
                                    sub_metric_name):
        skip_sample_values = \
            self.definitions.configurations['skip_sample_values']
        if actual_value in skip_sample_values:
            LOG.debug(
                "Skipping multi metric sample [%s] because "
                "value [%s] is configured to be skipped in "
                "skip list [%s].", sub_sample, actual_value,
                skip_sample_values)
            return True
        if sub_metric_name in skip_sample_values:
            LOG.debug(
                "Skipping sample [%s] because its sub-metric "
                "name [%s] is configured to be skipped in "
                "skip list [%s].", sub_sample, sub_metric_name,
                skip_sample_values)
            return True
        return False


class PollsterValueMapper(object):

    def __init__(self, definitions):
        self.definitions = definitions

    def map_or_skip_value(self, value, pollster_sample):
        skip_sample_values = \
            self.definitions.configurations['skip_sample_values']

        if value in skip_sample_values:
            LOG.debug("Skipping sample [%s] because value [%s] "
                      "is configured to be skipped in skip list [%s].",
                      pollster_sample, value, skip_sample_values)
            return SkippedSample()

        return self.execute_value_mapping(value)

    def execute_value_mapping(self, value):
        value_mapping = self.definitions.configurations['value_mapping']
        if not value_mapping:
            return value

        if value in value_mapping:
            old_value = value
            value = value_mapping[value]
            LOG.debug("Value mapped from [%s] to [%s]",
                      old_value, value)
        else:
            default_value = \
                self.definitions.configurations['default_value']
            LOG.warning(
                "Value [%s] was not found in value_mapping [%s]; "
                "therefore, we will use the default [%s].",
                value, value_mapping, default_value)
            value = default_value
        return value


class PollsterDefinition(object):
    """Represents a dynamic pollster configuration/parameter

    It abstract the job of developers when creating or extending parameters,
    such as validating parameters name, values and so on.
    """

    def __init__(self, name, required=False, on_missing=lambda df: df.default,
                 default=None, validation_regex=None, creatable=True,
                 validator=None):
        """Create a dynamic pollster configuration/parameter

        :param name: the name of the pollster parameter/configuration.
        :param required: indicates if the configuration/parameter is
               optional or not.
        :param on_missing: function that is executed when the
               parameter/configuration is missing.
        :param default: the default value to be used.
        :param validation_regex: the regular expression used to validate the
               name of the configuration/parameter.
        :param creatable: it is an override mechanism to avoid creating
               a configuration/parameter with the default value. The default
               is ``True``; therefore, we always use the default value.
               However, we can disable the use of the default value by
               setting ``False``. When we set this configuration to
               ``False``, the parameter is not added to the definition
               dictionary if not defined by the operator in the pollster
               YAML configuration file.
        :param validator: function used to validate the value of the
               parameter/configuration when it is given by the user. This
               function signature should receive a value that is the value of
               the parameter to be validate.
        """

        self.name = name
        self.required = required
        self.on_missing = on_missing
        self.validation_regex = validation_regex
        self.creatable = creatable
        self.default = default
        if self.validation_regex:
            self.validation_pattern = re.compile(self.validation_regex)
        self.validator = validator

    def validate(self, val):
        if val is None:
            return self.on_missing(self)
        if self.validation_regex and not self.validation_pattern.match(val):
            raise declarative.DynamicPollsterDefinitionException(
                "Pollster %s [%s] does not match [%s]."
                % (self.name, val, self.validation_regex))

        if self.validator:
            self.validator(val)

        return val


class PollsterDefinitions(object):

    POLLSTER_VALID_NAMES_REGEXP = r"^([\w-]+)(\.[\w-]+)*(\.{[\w-]+})?$"

    standard_definitions = [
        PollsterDefinition(name='name', required=True,
                           validation_regex=POLLSTER_VALID_NAMES_REGEXP),
        PollsterDefinition(name='sample_type', required=True,
                           validator=validate_sample_type),
        PollsterDefinition(name='unit', required=True),
        PollsterDefinition(name='endpoint_type', required=True),
        PollsterDefinition(name='url_path', required=True),
        PollsterDefinition(name='metadata_fields', creatable=False),
        PollsterDefinition(name='skip_sample_values', default=[]),
        PollsterDefinition(name='value_mapping', default={}),
        PollsterDefinition(name='default_value', default=-1),
        PollsterDefinition(name='metadata_mapping', default={}),
        PollsterDefinition(name='preserve_mapped_metadata', default=True),
        PollsterDefinition(name='response_entries_key'),
        PollsterDefinition(name='next_sample_url_attribute'),
        PollsterDefinition(name='user_id_attribute', default="user_id"),
        PollsterDefinition(name='resource_id_attribute', default="id"),
        PollsterDefinition(name='project_id_attribute', default="project_id"),
        PollsterDefinition(name='headers')]

    extra_definitions = []

    def __init__(self, configurations):
        self.configurations = configurations
        self.value_mapper = PollsterValueMapper(self)
        self.definitions = self.map_definitions()
        self.validate_configurations(configurations)
        self.validate_missing()
        self.sample_gatherer = PollsterSampleGatherer(self)
        self.sample_extractor = SimplePollsterSampleExtractor(self)

    def validate_configurations(self, configurations):
        for k, v in self.definitions.items():
            if configurations.get(k) is not None:
                self.configurations[k] = self.definitions[k].validate(
                    self.configurations[k])
            elif self.definitions[k].creatable:
                self.configurations[k] = self.definitions[k].default

    @staticmethod
    def is_field_applicable_to_definition(configurations):
        return True

    def map_definitions(self):
        definitions = dict(
            map(lambda df: (df.name, df), self.standard_definitions))
        extra_definitions = dict(
            map(lambda df: (df.name, df), self.extra_definitions))
        definitions.update(extra_definitions)
        return definitions

    def extract_attribute_key(self):
        pass

    def validate_missing(self):
        required_configurations = map(lambda fdf: fdf.name,
                                      filter(lambda df: df.required,
                                             self.definitions.values()))

        missing = list(filter(
            lambda rf: rf not in map(lambda f: f[0],
                                     filter(lambda f: f[1],
                                            self.configurations.items())),
            required_configurations))

        if missing:
            raise declarative.DynamicPollsterDefinitionException(
                "Required fields %s not specified."
                % missing, self.configurations)


class MultiMetricPollsterDefinitions(PollsterDefinitions):

    MULTI_METRIC_POLLSTER_NAME_REGEXP = r".*(\.{(\w+)})$"
    pattern_pollster_name = re.compile(
        MULTI_METRIC_POLLSTER_NAME_REGEXP)
    MULTI_METRIC_POLLSTER_VALUE_ATTRIBUTE_REGEXP = r"^(\[(\w+)\])((\.\w+)+)$"
    pattern_pollster_value_attribute = re.compile(
        MULTI_METRIC_POLLSTER_VALUE_ATTRIBUTE_REGEXP)

    extra_definitions = [
        PollsterDefinition(
            name='value_attribute', required=True,
            validation_regex=MULTI_METRIC_POLLSTER_VALUE_ATTRIBUTE_REGEXP),
    ]

    def __init__(self, configurations):
        super(MultiMetricPollsterDefinitions, self).__init__(configurations)
        self.sample_extractor = MultiMetricPollsterSampleExtractor(self)

    @staticmethod
    def is_field_applicable_to_definition(configurations):
        return configurations.get(
            'name') and MultiMetricPollsterDefinitions.\
            pattern_pollster_name.match(configurations['name'])

    def extract_attribute_key(self):
        return self.pattern_pollster_value_attribute.match(
            self.configurations['value_attribute']).group(2)


class SingleMetricPollsterDefinitions(PollsterDefinitions):

    extra_definitions = [
        PollsterDefinition(name='value_attribute', required=True)]

    def __init__(self, configurations):
        super(SingleMetricPollsterDefinitions, self).__init__(configurations)

    def extract_attribute_key(self):
        return self.configurations['value_attribute']

    @staticmethod
    def is_field_applicable_to_definition(configurations):
        return not MultiMetricPollsterDefinitions. \
            is_field_applicable_to_definition(configurations)


class PollsterSampleGatherer(object):

    def __init__(self, definitions):
        self.definitions = definitions

    @property
    def default_discovery(self):
        return 'endpoint:' + self.definitions.configurations['endpoint_type']

    def execute_request_get_samples(self, **kwargs):
        resp, url = self.definitions.sample_gatherer. \
            internal_execute_request_get_samples(kwargs)

        response_json = resp.json()
        entry_size = len(response_json)
        LOG.debug("Entries [%s] in the JSON for request [%s] "
                  "for dynamic pollster [%s].",
                  response_json, url, self.definitions.configurations['name'])

        if entry_size > 0:
            samples = self.retrieve_entries_from_response(response_json)
            url_to_next_sample = self.get_url_to_next_sample(response_json)
            if url_to_next_sample:
                kwargs['next_sample_url'] = url_to_next_sample
                samples += self.execute_request_get_samples(**kwargs)

            self.execute_id_overrides(samples)
            return samples
        return []

    def execute_id_overrides(self, samples):
        if samples:
            user_id_attribute = self.definitions.configurations[
                'user_id_attribute']
            project_id_attribute = self.definitions.configurations[
                'project_id_attribute']
            resource_id_attribute = self.definitions.configurations[
                'resource_id_attribute']

            for request_sample in samples:
                self.generate_new_attributes_in_sample(
                    request_sample, user_id_attribute, 'user_id')
                self.generate_new_attributes_in_sample(
                    request_sample, project_id_attribute, 'project_id')
                self.generate_new_attributes_in_sample(
                    request_sample, resource_id_attribute, 'id')

    def generate_new_attributes_in_sample(
            self, sample, attribute_key, new_attribute_key):

        if attribute_key == new_attribute_key:
            LOG.debug("We do not need to generate new attribute as the "
                      "attribute_key[%s] and the new_attribute_key[%s] "
                      "configurations are the same.",
                      attribute_key, new_attribute_key)
            return

        if attribute_key:
            attribute_value = self.definitions.sample_extractor.\
                retrieve_attribute_nested_value(sample, attribute_key)

            LOG.debug("Mapped attribute [%s] to value [%s] in sample [%s].",
                      attribute_key, attribute_value, sample)

            sample[new_attribute_key] = attribute_value

    def get_url_to_next_sample(self, resp):
        linked_sample_extractor = self.definitions.configurations[
            'next_sample_url_attribute']
        if not linked_sample_extractor:
            return None

        try:
            return self.definitions.sample_extractor.\
                retrieve_attribute_nested_value(resp, linked_sample_extractor)
        except KeyError:
            LOG.debug("There is no next sample url for the sample [%s] using "
                      "the configuration [%s]", resp, linked_sample_extractor)
        return None

    def internal_execute_request_get_samples(self, kwargs):
        keystone_client = kwargs['keystone_client']
        url = self.get_request_linked_samples_url(kwargs)

        request_arguments = self.create_request_arguments()
        LOG.debug("Executing request against [url=%s] with parameters ["
                  "%s] for pollsters [%s]", url, request_arguments,
                  self.definitions.configurations["name"])

        resp = keystone_client.session.get(url, **request_arguments)

        if resp.status_code != requests.codes.ok:
            resp.raise_for_status()
        return resp, url

    def create_request_arguments(self):
        request_args = {
            "authenticated": True
        }
        request_headers = self.definitions.configurations['headers']
        if request_headers:
            request_args['headers'] = request_headers
        return request_args

    def get_request_linked_samples_url(self, kwargs):
        next_sample_url = kwargs.get('next_sample_url')
        if next_sample_url:
            return self.get_next_page_url(kwargs, next_sample_url)
        return self.get_request_url(
            kwargs, self.definitions.configurations['url_path'])

    def get_next_page_url(self, kwargs, next_sample_url):
        parse_result = url_parse.urlparse(next_sample_url)
        if parse_result.netloc:
            return next_sample_url
        return self.get_request_url(kwargs, next_sample_url)

    def get_request_url(self, kwargs, url_path):
        endpoint = kwargs['resource']
        return url_parse.urljoin(endpoint, url_path)

    def retrieve_entries_from_response(self, response_json):
        if isinstance(response_json, list):
            return response_json

        first_entry_name = \
            self.definitions.configurations['response_entries_key']
        if not first_entry_name:
            try:
                first_entry_name = next(iter(response_json))
            except RuntimeError as e:
                LOG.debug("Generator threw a StopIteration "
                          "and we need to catch it [%s].", e)
        return self.definitions.sample_extractor. \
            retrieve_attribute_nested_value(response_json, first_entry_name)


class NonOpenStackApisPollsterDefinition(PollsterDefinitions):

    extra_definitions = [
        PollsterDefinition(name='value_attribute', required=True),
        PollsterDefinition(name='module', required=True),
        PollsterDefinition(name='authentication_object', required=True),
        PollsterDefinition(name='barbican_secret_id', default=""),
        PollsterDefinition(name='authentication_parameters', default=""),
        PollsterDefinition(name='endpoint_type')]

    def __init__(self, configurations):
        super(NonOpenStackApisPollsterDefinition, self).__init__(
            configurations)
        self.sample_gatherer = NonOpenStackApisSamplesGatherer(self)

    @staticmethod
    def is_field_applicable_to_definition(configurations):
        return configurations.get('module')


class NonOpenStackApisSamplesGatherer(PollsterSampleGatherer):

    @property
    def default_discovery(self):
        return 'barbican:' + \
               self.definitions.configurations['barbican_secret_id']

    def internal_execute_request_get_samples(self, kwargs):
        credentials = kwargs['resource']

        override_credentials = self.definitions.configurations[
            'authentication_parameters']
        if override_credentials:
            credentials = override_credentials

        url = self.get_request_linked_samples_url(kwargs)

        authenticator_module_name = self.definitions.configurations['module']
        authenticator_class_name = \
            self.definitions.configurations['authentication_object']

        imported_module = __import__(authenticator_module_name)
        authenticator_class = getattr(imported_module,
                                      authenticator_class_name)

        authenticator_arguments = list(map(str.strip, credentials.split(",")))
        authenticator_instance = authenticator_class(*authenticator_arguments)

        request_arguments = self.create_request_arguments()
        request_arguments["auth"] = authenticator_instance

        LOG.debug("Executing request against [url=%s] with parameters ["
                  "%s] for pollsters [%s]", url, request_arguments,
                  self.definitions.configurations["name"])
        resp = requests.get(url, **request_arguments)

        if resp.status_code != requests.codes.ok:
            raise declarative.NonOpenStackApisDynamicPollsterException(
                "Error while executing request[%s]."
                " Status[%s] and reason [%s]."
                % (url, resp.status_code, resp.reason))

        return resp, url

    def create_request_arguments(self):
        request_arguments = super(
            NonOpenStackApisSamplesGatherer, self).create_request_arguments()

        request_arguments.pop("authenticated")

        return request_arguments

    def get_request_url(self, kwargs, url_path):
        endpoint = self.definitions.configurations['url_path']
        if endpoint == url_path:
            return url_path
        return url_parse.urljoin(endpoint, url_path)

    def execute_request_get_samples(self, **kwargs):
        samples = super(NonOpenStackApisSamplesGatherer,
                        self).execute_request_get_samples(**kwargs)

        if samples:
            user_id_attribute = self.definitions.configurations[
                'user_id_attribute']
            project_id_attribute = self.definitions.configurations[
                'project_id_attribute']
            resource_id_attribute = self.definitions.configurations[
                'resource_id_attribute']

            for request_sample in samples:
                self.generate_new_attributes_in_sample(
                    request_sample, user_id_attribute, 'user_id')
                self.generate_new_attributes_in_sample(
                    request_sample, project_id_attribute, 'project_id')
                self.generate_new_attributes_in_sample(
                    request_sample, resource_id_attribute, 'id')

        return samples

    def generate_new_attributes_in_sample(
            self, sample, attribute_key, new_attribute_key):
        if attribute_key:
            attribute_value = self.definitions.sample_extractor. \
                retrieve_attribute_nested_value(sample, attribute_key)

            LOG.debug("Mapped attribute [%s] to value [%s] in sample [%s].",
                      attribute_key, attribute_value, sample)

            sample[new_attribute_key] = attribute_value


class SkippedSample(object):
    pass


class DynamicPollster(plugin_base.PollsterBase):
    # Mandatory name field
    name = ""

    def __init__(self, pollster_definitions={}, conf=None,
                 supported_definitions=[NonOpenStackApisPollsterDefinition,
                                        MultiMetricPollsterDefinitions,
                                        SingleMetricPollsterDefinitions]):
        super(DynamicPollster, self).__init__(conf)
        self.supported_definitions = supported_definitions
        LOG.debug("%s instantiated with [%s]", __name__,
                  pollster_definitions)

        self.definitions = PollsterDefinitionBuilder(
            self.supported_definitions).build_definitions(pollster_definitions)
        self.pollster_definitions = self.definitions.configurations
        if 'metadata_fields' in self.pollster_definitions:
            LOG.debug("Metadata fields configured to [%s].",
                      self.pollster_definitions['metadata_fields'])

        self.name = self.pollster_definitions['name']
        self.obj = self

    @property
    def default_discovery(self):
        return self.definitions.sample_gatherer.default_discovery

    def load_samples(self, resource, manager):
        try:
            return self.definitions.sample_gatherer.\
                execute_request_get_samples(keystone_client=manager._keystone,
                                            resource=resource)
        except RequestException as e:
            LOG.warning("Error [%s] while loading samples for [%s] "
                        "for dynamic pollster [%s].",
                        e, resource, self.name)

        return list([])

    def get_samples(self, manager, cache, resources):
        if not resources:
            LOG.debug("No resources received for processing.")
            yield None

        for r in resources:
            LOG.debug("Executing get sample for resource [%s].", r)
            samples = self.load_samples(r, manager)
            for pollster_sample in samples:
                sample = self.extract_sample(pollster_sample)
                if isinstance(sample, SkippedSample):
                    continue
                yield from sample

    def extract_sample(self, pollster_sample):
        return self.definitions.sample_extractor.extract_sample(
            pollster_sample)
