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


"""Non-OpenStack Dynamic pollster component
    This component enables operators to create pollsters on the fly
    via configuration for non-OpenStack APIs. This appraoch is quite
    useful when adding metrics from APIs such as RadosGW into the Cloud
    rating and billing modules.
"""
import copy
import requests

from ceilometer.declarative import NonOpenStackApisDynamicPollsterException
from ceilometer.polling.dynamic_pollster import DynamicPollster
from oslo_log import log

LOG = log.getLogger(__name__)


class NonOpenStackApisDynamicPollster(DynamicPollster):

    POLLSTER_REQUIRED_POLLSTER_FIELDS = ['module', 'authentication_object']

    POLLSTER_OPTIONAL_POLLSTER_FIELDS = ['user_id_attribute',
                                         'project_id_attribute',
                                         'resource_id_attribute',
                                         'barbican_secret_id',
                                         'authentication_parameters'
                                         ]

    def __init__(self, pollster_definitions, conf=None):
        # Making sure that we do not change anything in parent classes
        self.REQUIRED_POLLSTER_FIELDS = copy.deepcopy(
            DynamicPollster.REQUIRED_POLLSTER_FIELDS)
        self.OPTIONAL_POLLSTER_FIELDS = copy.deepcopy(
            DynamicPollster.OPTIONAL_POLLSTER_FIELDS)

        # Non-OpenStack dynamic pollster do not need the 'endpoint_type'.
        self.REQUIRED_POLLSTER_FIELDS.remove('endpoint_type')

        self.REQUIRED_POLLSTER_FIELDS += self.POLLSTER_REQUIRED_POLLSTER_FIELDS
        self.OPTIONAL_POLLSTER_FIELDS += self.POLLSTER_OPTIONAL_POLLSTER_FIELDS

        super(NonOpenStackApisDynamicPollster, self).__init__(
            pollster_definitions, conf)

    def set_default_values(self):
        super(NonOpenStackApisDynamicPollster, self).set_default_values()

        if 'user_id_attribute' not in self.pollster_definitions:
            self.pollster_definitions['user_id_attribute'] = None

        if 'project_id_attribute' not in self.pollster_definitions:
            self.pollster_definitions['project_id_attribute'] = None

        if 'resource_id_attribute' not in self.pollster_definitions:
            self.pollster_definitions['resource_id_attribute'] = None

        if 'barbican_secret_id' not in self.pollster_definitions:
            self.pollster_definitions['barbican_secret_id'] = ""

        if 'authentication_parameters' not in self.pollster_definitions:
            self.pollster_definitions['authentication_parameters'] = ""

    @property
    def default_discovery(self):
        return 'barbican:' + self.pollster_definitions['barbican_secret_id']

    def internal_execute_request_get_samples(self, kwargs):
        credentials = kwargs['resource']

        override_credentials = self.pollster_definitions[
            'authentication_parameters']
        if override_credentials:
            credentials = override_credentials

        url = self.pollster_definitions['url_path']

        authenticator_module_name = self.pollster_definitions['module']
        authenticator_class_name = \
            self.pollster_definitions['authentication_object']

        imported_module = __import__(authenticator_module_name)
        authenticator_class = getattr(imported_module,
                                      authenticator_class_name)

        authenticator_arguments = list(map(str.strip, credentials.split(",")))
        authenticator_instance = authenticator_class(*authenticator_arguments)

        resp = requests.get(
            url,
            auth=authenticator_instance)

        if resp.status_code != requests.codes.ok:
            raise NonOpenStackApisDynamicPollsterException(
                "Error while executing request[%s]."
                " Status[%s] and reason [%s]."
                % (url, resp.status_code, resp.reason))

        return resp, url

    def execute_request_get_samples(self, **kwargs):
        samples = super(NonOpenStackApisDynamicPollster,
                        self).execute_request_get_samples(**kwargs)

        if samples:
            user_id_attribute = self.pollster_definitions[
                'user_id_attribute']
            project_id_attribute = self.pollster_definitions[
                'project_id_attribute']
            resource_id_attribute = self.pollster_definitions[
                'resource_id_attribute']

            for sample in samples:
                self.generate_new_attributes_in_sample(
                    sample, user_id_attribute, 'user_id')
                self.generate_new_attributes_in_sample(
                    sample, project_id_attribute, 'project_id')
                self.generate_new_attributes_in_sample(
                    sample, resource_id_attribute, 'id')

        return samples

    def generate_new_attributes_in_sample(
            self, sample, attribute_key, new_attribute_key):
        if attribute_key:
            attribute_value = self.retrieve_attribute_nested_value(
                sample, attribute_key)

            LOG.debug("Mapped attribute [%s] to value [%s] in sample [%s].",
                      attribute_key, attribute_value, sample)

            sample[new_attribute_key] = attribute_value
