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
import json
import re
import subprocess
import time
import xmltodict

from oslo_log import log

from requests import RequestException

from ceilometer import declarative
from ceilometer.polling import plugin_base
from ceilometer import sample as ceilometer_sample
from ceilometer import utils as ceilometer_utils

from functools import reduce
import operator
import requests

from urllib import parse as urlparse

LOG = log.getLogger(__name__)


def validate_sample_type(sample_type):
    if sample_type not in ceilometer_sample.TYPES:
        raise declarative.DynamicPollsterDefinitionException(
            "Invalid sample type [%s]. Valid ones are [%s]."
            % (sample_type, ceilometer_sample.TYPES))


class XMLResponseHandler(object):
    """This response handler converts an XML in string format to a dict"""

    @staticmethod
    def handle(response):
        return xmltodict.parse(response)


class JsonResponseHandler(object):
    """This response handler converts a JSON in string format to a dict"""

    @staticmethod
    def handle(response):
        return json.loads(response)


class PlainTextResponseHandler(object):
    """Response handler converts string to a list of dict [{'out'=<string>}]"""

    @staticmethod
    def handle(response):
        return [{'out': str(response)}]


VALID_HANDLERS = {
    'json': JsonResponseHandler,
    'xml': XMLResponseHandler,
    'text': PlainTextResponseHandler
}


def validate_response_handler(val):
    if not isinstance(val, list):
        raise declarative.DynamicPollsterDefinitionException(
            "Invalid response_handlers configuration. It must be a list. "
            "Provided value type: %s" % type(val).__name__)

    for value in val:
        if value not in VALID_HANDLERS:
            raise declarative.DynamicPollsterDefinitionException(
                "Invalid response_handler value [%s]. Accepted values "
                "are [%s]" % (value, ', '.join(list(VALID_HANDLERS))))


def validate_extra_metadata_skip_samples(val):
    if not isinstance(val, list) or next(
            filter(lambda v: not isinstance(v, dict), val), None):
        raise declarative.DynamicPollsterDefinitionException(
            "Invalid extra_metadata_fields_skip configuration."
            " It must be a list of maps. Provided value: %s,"
            " value type: %s." % (val, type(val).__name__))


class ResponseHandlerChain(object):
    """Tries to convert a string to a dict using the response handlers"""

    def __init__(self, response_handlers, **meta):
        if not isinstance(response_handlers, list):
            response_handlers = list(response_handlers)

        self.response_handlers = response_handlers
        self.meta = meta

    def handle(self, response):
        failed_handlers = []
        for handler in self.response_handlers:
            try:
                return handler.handle(response)
            except Exception as e:
                handler_name = handler.__name__
                failed_handlers.append(handler_name)
                LOG.debug(
                    "Error handling response [%s] with handler [%s]: %s. "
                    "We will try the next one, if multiple handlers were "
                    "configured.",
                    response, handler_name, e)

        handlers_str = ', '.join(failed_handlers)
        raise declarative.InvalidResponseTypeException(
            "No remaining handlers to handle the response [%s], "
            "used handlers [%s]. [%s]." % (response, handlers_str, self.meta))


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

    def generate_sample(
            self, pollster_sample, pollster_definitions=None, **kwargs):

        pollster_definitions =\
            pollster_definitions or self.definitions.configurations

        metadata = dict()
        if 'metadata_fields' in pollster_definitions:
            for k in pollster_definitions['metadata_fields']:
                val = self.retrieve_attribute_nested_value(
                    pollster_sample, value_attribute=k,
                    definitions=self.definitions.configurations)

                LOG.debug("Assigning value [%s] to metadata key [%s].", val, k)
                metadata[k] = val

        self.generate_new_metadata_fields(
            metadata=metadata, pollster_definitions=pollster_definitions)

        pollster_sample['metadata'] = metadata
        extra_metadata = self.definitions.retrieve_extra_metadata(
            kwargs['manager'], pollster_sample, kwargs['conf'])

        LOG.debug("Extra metadata [%s] collected for sample [%s].",
                  extra_metadata, pollster_sample)
        for key in extra_metadata.keys():
            if key in metadata.keys():
                LOG.warning("The extra metadata key [%s] already exist in "
                            "pollster current metadata set [%s]. Therefore, "
                            "we will ignore it with its value [%s].",
                            key, metadata, extra_metadata[key])
                continue
            metadata[key] = extra_metadata[key]

        return ceilometer_sample.Sample(
            timestamp=ceilometer_utils.isotime(),
            name=pollster_definitions['name'],
            type=pollster_definitions['sample_type'],
            unit=pollster_definitions['unit'],
            volume=pollster_sample['value'],
            user_id=pollster_sample.get("user_id"),
            project_id=pollster_sample.get("project_id"),
            resource_id=pollster_sample.get("id"),
            resource_metadata=metadata)

    def retrieve_attribute_nested_value(self, json_object,
                                        value_attribute=None,
                                        definitions=None, **kwargs):
        if not definitions:
            definitions = self.definitions.configurations

        attribute_key = value_attribute
        if not attribute_key:
            attribute_key = self.definitions.extract_attribute_key()

        LOG.debug(
            "Retrieving the nested keys [%s] from [%s] or pollster [""%s].",
            attribute_key, json_object, definitions["name"])

        keys_and_operations = attribute_key.split("|")
        attribute_key = keys_and_operations[0].strip()

        if attribute_key == ".":
            value = json_object
        else:
            nested_keys = attribute_key.split(".")
            value = reduce(operator.getitem, nested_keys, json_object)

        return self.operate_value(keys_and_operations, value, definitions)

    def operate_value(self, keys_and_operations, value, definitions):
        # We do not have operations to be executed against the value extracted
        if len(keys_and_operations) < 2:
            return value
        for operation in keys_and_operations[1::]:
            # The operation must be performed onto the 'value' variable
            if 'value' not in operation:
                raise declarative.DynamicPollsterDefinitionException(
                    "The attribute field operation [%s] must use the ["
                    "value] variable." % operation, definitions)

            LOG.debug("Executing operation [%s] against value[%s] for "
                      "pollster [%s].", operation, value,
                      definitions["name"])

            value = eval(operation.strip())
            LOG.debug("Result [%s] of operation [%s] for pollster [%s].",
                      value, operation, definitions["name"])
        return value


class SimplePollsterSampleExtractor(PollsterSampleExtractor):

    def generate_single_sample(self, pollster_sample, **kwargs):
        value = self.retrieve_attribute_nested_value(
            pollster_sample)
        value = self.definitions.value_mapper.map_or_skip_value(
            value, pollster_sample)

        if isinstance(value, SkippedSample):
            return value

        pollster_sample['value'] = value

        return self.generate_sample(pollster_sample, **kwargs)

    def extract_sample(self, pollster_sample, **kwargs):
        sample = self.generate_single_sample(pollster_sample, **kwargs)
        if isinstance(sample, SkippedSample):
            return sample
        yield sample


class MultiMetricPollsterSampleExtractor(PollsterSampleExtractor):

    def extract_sample(self, pollster_sample, **kwargs):
        pollster_definitions = self.definitions.configurations

        value = self.retrieve_attribute_nested_value(
            pollster_sample, definitions=pollster_definitions)
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
                                            pollster_sample, **kwargs)

    def extract_sub_samples(self, value, sub_metric_attribute_name,
                            pollster_name, value_attribute,
                            sub_metric_placeholder, pollster_definitions,
                            pollster_sample, **kwargs):

        for sub_sample in value:
            sub_metric_name = sub_sample[sub_metric_attribute_name]
            new_metric_name = pollster_name.replace(
                sub_metric_placeholder, sub_metric_name)
            pollster_definitions['name'] = new_metric_name

            actual_value = self.retrieve_attribute_nested_value(
                sub_sample, value_attribute, definitions=pollster_definitions)

            pollster_sample['value'] = actual_value

            if self.should_skip_generate_sample(actual_value, sub_sample,
                                                sub_metric_name):
                continue

            yield self.generate_sample(
                pollster_sample, pollster_definitions, **kwargs)

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

    EXTERNAL_ENDPOINT_TYPE = "external"

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
        PollsterDefinition(name='headers'),
        PollsterDefinition(name='timeout', default=30),
        PollsterDefinition(name='extra_metadata_fields_cache_seconds',
                           default=3600),
        PollsterDefinition(name='extra_metadata_fields'),
        PollsterDefinition(name='extra_metadata_fields_skip', default=[{}],
                           validator=validate_extra_metadata_skip_samples),
        PollsterDefinition(name='response_handlers', default=['json'],
                           validator=validate_response_handler),
        PollsterDefinition(name='base_metadata', default={})
    ]

    extra_definitions = []

    def __init__(self, configurations):
        self.configurations = configurations
        self.value_mapper = PollsterValueMapper(self)
        self.definitions = self.map_definitions()
        self.validate_configurations(configurations)
        self.validate_missing()
        self.sample_gatherer = PollsterSampleGatherer(self)
        self.sample_extractor = SimplePollsterSampleExtractor(self)
        self.response_cache = {}

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

    def should_skip_extra_metadata(self, skip, sample):
        match_msg = "Sample [%s] %smatches with configured" \
                    " extra_metadata_fields_skip [%s]."
        if skip == sample:
            LOG.debug(match_msg, sample, "", skip)
            return True
        if not isinstance(skip, dict) or not isinstance(sample, dict):
            LOG.debug(match_msg, sample, "not ", skip)
            return False

        for key in skip:
            if key not in sample:
                LOG.debug(match_msg, sample, "not ", skip)
                return False
            if not self.should_skip_extra_metadata(skip[key], sample[key]):
                LOG.debug(match_msg, sample, "not ", skip)
                return False

        LOG.debug(match_msg, sample, "", skip)
        return True

    def skip_sample(self, request_sample, skips):
        for skip in skips:
            if not skip:
                continue
            if self.should_skip_extra_metadata(skip, request_sample):
                LOG.debug("Skipping extra_metadata_field gathering for "
                          "sample [%s] as defined in the "
                          "extra_metadata_fields_skip [%s]", request_sample,
                          skip)
                return True
        return False

    def retrieve_extra_metadata(self, manager, request_sample, pollster_conf):
        extra_metadata_fields = self.configurations['extra_metadata_fields']
        if extra_metadata_fields:
            extra_metadata_samples = {}
            extra_metadata_by_name = {}
            if not isinstance(extra_metadata_fields, (list, tuple)):
                extra_metadata_fields = [extra_metadata_fields]
            for ext_metadata in extra_metadata_fields:
                ext_metadata.setdefault(
                    'extra_metadata_fields_skip',
                    self.configurations['extra_metadata_fields_skip'])
                ext_metadata.setdefault(
                    'sample_type', self.configurations['sample_type'])
                ext_metadata.setdefault('unit', self.configurations['unit'])
                ext_metadata.setdefault(
                    'value_attribute', ext_metadata.get(
                        'value', self.configurations['value_attribute']))
                ext_metadata['base_metadata'] = {
                    'extra_metadata_captured': extra_metadata_samples,
                    'extra_metadata_by_name': extra_metadata_by_name,
                    'sample': request_sample
                }
                parent_cache_ttl = self.configurations[
                    'extra_metadata_fields_cache_seconds']
                cache_ttl = ext_metadata.get(
                    'extra_metadata_fields_cache_seconds', parent_cache_ttl
                )
                response_cache = self.response_cache
                extra_metadata_pollster = DynamicPollster(
                    ext_metadata, conf=pollster_conf, cache_ttl=cache_ttl,
                    extra_metadata_responses_cache=response_cache,
                )

                skips = ext_metadata['extra_metadata_fields_skip']
                if self.skip_sample(request_sample, skips):
                    continue

                resources = [None]
                if ext_metadata.get('endpoint_type'):
                    resources = manager.discover([
                        extra_metadata_pollster.default_discovery], {})
                samples = extra_metadata_pollster.get_samples(
                    manager, None, resources)
                for sample in samples:
                    self.fill_extra_metadata_samples(
                        extra_metadata_by_name,
                        extra_metadata_samples,
                        sample)
            return extra_metadata_samples

        LOG.debug("No extra metadata to be captured for pollsters [%s] and "
                  "request sample [%s].", self.definitions, request_sample)
        return {}

    def fill_extra_metadata_samples(self, extra_metadata_by_name,
                                    extra_metadata_samples, sample):
        extra_metadata_samples[sample.name] = sample.volume
        LOG.debug("Merging the sample metadata [%s] of the "
                  "extra_metadata_field [%s], with the "
                  "extra_metadata_samples [%s].",
                  sample.resource_metadata,
                  sample.name,
                  extra_metadata_samples)
        for key, value in sample.resource_metadata.items():
            if value is None and key in extra_metadata_samples:
                LOG.debug("Metadata [%s] for extra_metadata_field [%s] "
                          "is None, skipping metadata override by None "
                          "value", key, sample.name)
                continue
            extra_metadata_samples[key] = value
        extra_metadata_by_name[sample.name] = {
            'value': sample.volume,
            'metadata': sample.resource_metadata
        }

        LOG.debug("extra_metadata_samples after merging: [%s].",
                  extra_metadata_samples)


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
        self.response_handler_chain = ResponseHandlerChain(
            map(VALID_HANDLERS.get,
                self.definitions.configurations['response_handlers']),
            url_path=definitions.configurations['url_path']
        )

    def get_cache_key(self, definitions, **kwargs):
        return self.get_request_linked_samples_url(kwargs, definitions)

    def get_cached_response(self, definitions, **kwargs):
        if self.definitions.cache_ttl == 0:
            return
        cache_key = self.get_cache_key(definitions, **kwargs)
        response_cache = self.definitions.response_cache
        cached_response, max_ttl_for_cache = response_cache.get(
            cache_key, (None, None))

        current_time = time.time()
        if cached_response and max_ttl_for_cache >= current_time:
            LOG.debug("Returning response [%s] for request [%s] as the TTL "
                      "[max=%s, current_time=%s] has not expired yet.",
                      cached_response, definitions,
                      max_ttl_for_cache, current_time)
            return cached_response

        if cached_response and max_ttl_for_cache < current_time:
            LOG.debug("Cleaning cached response [%s] for request [%s] "
                      "as the TTL [max=%s, current_time=%s] has expired.",
                      cached_response, definitions,
                      max_ttl_for_cache, current_time)
            response_cache.pop(cache_key, None)

    def store_cached_response(self, definitions, resp, **kwargs):
        if self.definitions.cache_ttl == 0:
            return
        cache_key = self.get_cache_key(definitions, **kwargs)
        extra_metadata_fields_cache_seconds = self.definitions.cache_ttl
        max_ttl_for_cache = time.time() + extra_metadata_fields_cache_seconds

        cache_tuple = (resp, max_ttl_for_cache)
        self.definitions.response_cache[cache_key] = cache_tuple

    @property
    def default_discovery(self):
        return 'endpoint:' + self.definitions.configurations['endpoint_type']

    def execute_request_get_samples(self, **kwargs):
        return self.execute_request_for_definitions(
            self.definitions.configurations, **kwargs)

    def execute_request_for_definitions(self, definitions, **kwargs):
        if response_dict := self.get_cached_response(definitions, **kwargs):
            url = 'cached'
        else:
            resp, url = self._internal_execute_request_get_samples(
                definitions=definitions, **kwargs)
            response_dict = self.response_handler_chain.handle(resp.text)
            self.store_cached_response(definitions, response_dict, **kwargs)

        entry_size = len(response_dict)
        LOG.debug("Entries [%s] in the DICT for request [%s] "
                  "for dynamic pollster [%s].",
                  response_dict, url, definitions['name'])

        if entry_size > 0:
            samples = self.retrieve_entries_from_response(
                response_dict, definitions)
            url_to_next_sample = self.get_url_to_next_sample(
                response_dict, definitions)

            self.prepare_samples(definitions, samples, **kwargs)

            if url_to_next_sample:
                kwargs['next_sample_url'] = url_to_next_sample
                samples += self.execute_request_for_definitions(
                    definitions=definitions, **kwargs)
            return samples
        return []

    def prepare_samples(
            self, definitions, samples, execute_id_overrides=True, **kwargs):
        if samples and execute_id_overrides:
            for request_sample in samples:
                user_id_attribute = definitions.get(
                    'user_id_attribute', 'user_id')
                project_id_attribute = definitions.get(
                    'project_id_attribute', 'project_id')
                resource_id_attribute = definitions.get(
                    'resource_id_attribute', 'id')

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

    def get_url_to_next_sample(self, resp, definitions):
        linked_sample_extractor = definitions.get('next_sample_url_attribute')

        if not linked_sample_extractor:
            return None

        try:
            return self.definitions.sample_extractor.\
                retrieve_attribute_nested_value(resp, linked_sample_extractor)
        except KeyError:
            LOG.debug("There is no next sample url for the sample [%s] using "
                      "the configuration [%s]", resp, linked_sample_extractor)
        return None

    def _internal_execute_request_get_samples(self, definitions=None,
                                              keystone_client=None, **kwargs):
        if not definitions:
            definitions = self.definitions.configurations

        url = self.get_request_linked_samples_url(kwargs, definitions)
        request_arguments = self.create_request_arguments(definitions)
        LOG.debug("Executing request against [url=%s] with parameters ["
                  "%s] for pollsters [%s]", url, request_arguments,
                  definitions["name"])
        resp = keystone_client.session.get(url, **request_arguments)
        if resp.status_code != requests.codes.ok:
            resp.raise_for_status()
        return resp, url

    def create_request_arguments(self, definitions):
        request_args = {
            "authenticated": True
        }
        request_headers = definitions.get('headers', [])
        if request_headers:
            request_args['headers'] = request_headers
        request_args['timeout'] = definitions.get('timeout', 300)
        return request_args

    def get_request_linked_samples_url(self, kwargs, definitions):
        next_sample_url = kwargs.get('next_sample_url')
        if next_sample_url:
            return self.get_next_page_url(kwargs, next_sample_url)

        LOG.debug("Generating url with [%s] and path [%s].",
                  kwargs, definitions['url_path'])
        return self.get_request_url(
            kwargs, definitions['url_path'])

    def get_next_page_url(self, kwargs, next_sample_url):
        parse_result = urlparse.urlparse(next_sample_url)
        if parse_result.netloc:
            return next_sample_url
        return self.get_request_url(kwargs, next_sample_url)

    def get_request_url(self, kwargs, url_path):
        endpoint = kwargs['resource']
        params = copy.deepcopy(
            self.definitions.configurations.get(
                'base_metadata', {}))
        try:
            url_path = eval(url_path, params)
        except Exception:
            LOG.debug("Cannot eval path [%s] with params [%s],"
                      " using [%s] instead.",
                      url_path, params, url_path)
        return urlparse.urljoin(endpoint, url_path)

    def retrieve_entries_from_response(self, response_json, definitions):
        if isinstance(response_json, list):
            return response_json

        first_entry_name = definitions.get('response_entries_key')

        if not first_entry_name:
            try:
                first_entry_name = next(iter(response_json))
            except RuntimeError as e:
                LOG.debug("Generator threw a StopIteration "
                          "and we need to catch it [%s].", e)
        return self.definitions.sample_extractor.\
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


class HostCommandPollsterDefinition(PollsterDefinitions):

    extra_definitions = [
        PollsterDefinition(name='endpoint_type', required=False),
        PollsterDefinition(name='url_path', required=False),
        PollsterDefinition(name='host_command', required=True)]

    def __init__(self, configurations):
        super(HostCommandPollsterDefinition, self).__init__(
            configurations)
        self.sample_gatherer = HostCommandSamplesGatherer(self)

    @staticmethod
    def is_field_applicable_to_definition(configurations):
        return configurations.get('host_command')


class HostCommandSamplesGatherer(PollsterSampleGatherer):

    class Response(object):
        def __init__(self, text):
            self.text = text

    def get_cache_key(self, definitions, **kwargs):
        return self.get_command(definitions)

    def _internal_execute_request_get_samples(self, definitions, **kwargs):
        command = self.get_command(definitions, **kwargs)
        LOG.debug('Running Host command: [%s]', command)
        result = subprocess.getoutput(command)
        LOG.debug('Host command [%s] result: [%s]', command, result)
        return self.Response(result), command

    def get_command(self, definitions, next_sample_url=None, **kwargs):
        command = next_sample_url or definitions['host_command']
        params = copy.deepcopy(
            self.definitions.configurations.get(
                'base_metadata', {}))
        try:
            command = eval(command, params)
        except Exception:
            LOG.debug("Cannot eval command [%s] with params [%s],"
                      " using [%s] instead.",
                      command, params, command)
        return command

    @property
    def default_discovery(self):
        return 'local_node'


class NonOpenStackApisSamplesGatherer(PollsterSampleGatherer):

    @property
    def default_discovery(self):
        return 'barbican:' + \
               self.definitions.configurations['barbican_secret_id']

    def _internal_execute_request_get_samples(self, definitions, **kwargs):
        credentials = kwargs['resource']

        override_credentials = definitions['authentication_parameters']
        if override_credentials:
            credentials = override_credentials

        if not isinstance(credentials, str):
            credentials = self.normalize_credentials_to_string(credentials)

        url = self.get_request_linked_samples_url(kwargs, definitions)

        authenticator_module_name = definitions['module']
        authenticator_class_name = definitions['authentication_object']

        imported_module = __import__(authenticator_module_name)
        authenticator_class = getattr(imported_module,
                                      authenticator_class_name)

        authenticator_arguments = list(map(str.strip, credentials.split(",")))
        authenticator_instance = authenticator_class(*authenticator_arguments)

        request_arguments = self.create_request_arguments(definitions)
        request_arguments["auth"] = authenticator_instance

        LOG.debug("Executing request against [url=%s] with parameters ["
                  "%s] for pollsters [%s]", url, request_arguments,
                  definitions["name"])
        resp = requests.get(url, **request_arguments)

        if resp.status_code != requests.codes.ok:
            raise declarative.NonOpenStackApisDynamicPollsterException(
                "Error while executing request[%s]."
                " Status[%s] and reason [%s]."
                % (url, resp.status_code, resp.reason))

        return resp, url

    @staticmethod
    def normalize_credentials_to_string(credentials):
        if isinstance(credentials, bytes):
            credentials = credentials.decode('utf-8')
        else:
            credentials = str(credentials)
        LOG.debug("Credentials [%s] were not defined as a string. "
                  "Therefore, we converted it to a string like object.",
                  credentials)
        return credentials

    def create_request_arguments(self, definitions):
        request_arguments = super(
            NonOpenStackApisSamplesGatherer, self).create_request_arguments(
            definitions)

        request_arguments.pop("authenticated")

        return request_arguments

    def get_request_url(self, kwargs, url_path):
        endpoint = self.definitions.configurations['url_path']
        if endpoint == url_path:
            return url_path
        return urlparse.urljoin(endpoint, url_path)

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

    def __init__(self, pollster_definitions={}, conf=None, cache_ttl=0,
                 extra_metadata_responses_cache=None,
                 supported_definitions=[HostCommandPollsterDefinition,
                                        NonOpenStackApisPollsterDefinition,
                                        MultiMetricPollsterDefinitions,
                                        SingleMetricPollsterDefinitions]):
        super(DynamicPollster, self).__init__(conf)
        self.supported_definitions = supported_definitions
        LOG.debug("%s instantiated with [%s]", __name__,
                  pollster_definitions)

        self.definitions = PollsterDefinitionBuilder(
            self.supported_definitions).build_definitions(pollster_definitions)
        self.definitions.cache_ttl = cache_ttl
        self.definitions.response_cache = extra_metadata_responses_cache
        if extra_metadata_responses_cache is None:
            self.definitions.response_cache = {}
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
                execute_request_get_samples(manager=manager,
                                            resource=resource,
                                            keystone_client=manager._keystone)
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
            if not isinstance(samples, (list, tuple)):
                samples = [samples]
            for pollster_sample in samples:
                sample = self.extract_sample(
                    pollster_sample, manager=manager,
                    resource=r, conf=self.conf)
                if isinstance(sample, SkippedSample):
                    continue
                yield from sample

    def extract_sample(self, pollster_sample, **kwargs):
        return self.definitions.sample_extractor.extract_sample(
            pollster_sample, **kwargs)
