# Copyright 2014 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_serialization import jsonutils as json
from six.moves.urllib import parse as urllib

from tempest import config
from tempest.lib.common import rest_client
from tempest.lib.services.compute.flavors_client import FlavorsClient
from tempest.lib.services.compute.floating_ips_client import FloatingIPsClient
from tempest.lib.services.compute.networks_client import NetworksClient
from tempest.lib.services.compute.servers_client import ServersClient
from tempest import manager
from tempest.services.image.v1.json.images_client import ImagesClient
from tempest.services.image.v2.json.images_client import ImagesClientV2
from tempest.services.object_storage.container_client import ContainerClient
from tempest.services.object_storage.object_client import ObjectClient


CONF = config.CONF


class TelemetryClient(rest_client.RestClient):

    version = '2'
    uri_prefix = "v2"

    def deserialize(self, body):
        return json.loads(body.replace("\n", ""))

    def serialize(self, body):
        return json.dumps(body)

    def create_sample(self, meter_name, sample_list):
        uri = "%s/meters/%s" % (self.uri_prefix, meter_name)
        body = self.serialize(sample_list)
        resp, body = self.post(uri, body)
        self.expected_success(200, resp.status)
        body = self.deserialize(body)
        return rest_client.ResponseBody(resp, body)

    def _helper_list(self, uri, query=None, period=None):
        uri_dict = {}
        if query:
            uri_dict = {'q.field': query[0],
                        'q.op': query[1],
                        'q.value': query[2]}
        if period:
            uri_dict['period'] = period
        if uri_dict:
            uri += "?%s" % urllib.urlencode(uri_dict)
        resp, body = self.get(uri)
        self.expected_success(200, resp.status)
        body = self.deserialize(body)
        return rest_client.ResponseBodyList(resp, body)

    def list_resources(self, query=None):
        uri = '%s/resources' % self.uri_prefix
        return self._helper_list(uri, query)

    def list_meters(self, query=None):
        uri = '%s/meters' % self.uri_prefix
        return self._helper_list(uri, query)

    def list_statistics(self, meter, period=None, query=None):
        uri = "%s/meters/%s/statistics" % (self.uri_prefix, meter)
        return self._helper_list(uri, query, period)

    def list_samples(self, meter_id, query=None):
        uri = '%s/meters/%s' % (self.uri_prefix, meter_id)
        return self._helper_list(uri, query)

    def list_events(self, query=None):
        uri = '%s/events' % self.uri_prefix
        return self._helper_list(uri, query)

    def show_resource(self, resource_id):
        uri = '%s/resources/%s' % (self.uri_prefix, resource_id)
        resp, body = self.get(uri)
        self.expected_success(200, resp.status)
        body = self.deserialize(body)
        return rest_client.ResponseBody(resp, body)


class Manager(manager.Manager):

    load_clients = [
        'servers_client',
        'compute_networks_client',
        'compute_floating_ips_client',
        'flavors_client',
        'image_client',
        'image_client_v2',
        'telemetry_client',
        'container_client',
        'object_client',
    ]

    default_params = {
        'disable_ssl_certificate_validation':
            CONF.identity.disable_ssl_certificate_validation,
        'ca_certs': CONF.identity.ca_certificates_file,
        'trace_requests': CONF.debug.trace_requests
    }

    compute_params = {
        'service': CONF.compute.catalog_type,
        'region': CONF.compute.region or CONF.identity.region,
        'endpoint_type': CONF.compute.endpoint_type,
        'build_interval': CONF.compute.build_interval,
        'build_timeout': CONF.compute.build_timeout,
    }
    compute_params.update(default_params)

    image_params = {
        'catalog_type': CONF.image.catalog_type,
        'region': CONF.image.region or CONF.identity.region,
        'endpoint_type': CONF.image.endpoint_type,
        'build_interval': CONF.image.build_interval,
        'build_timeout': CONF.image.build_timeout,
    }
    image_params.update(default_params)

    telemetry_params = {
        'service': CONF.telemetry_plugin.catalog_type,
        'region': CONF.identity.region,
        'endpoint_type': CONF.telemetry_plugin.endpoint_type,
    }
    telemetry_params.update(default_params)

    object_storage_params = {
        'service': CONF.object_storage.catalog_type,
        'region': CONF.object_storage.region or CONF.identity.region,
        'endpoint_type': CONF.object_storage.endpoint_type
    }
    object_storage_params.update(default_params)

    def __init__(self, credentials=None, service=None):
        super(Manager, self).__init__(credentials)
        for client in self.load_clients:
            getattr(self, 'set_%s' % client)()

    def set_servers_client(self):
        self.servers_client = ServersClient(self.auth_provider,
                                            **self.compute_params)

    def set_compute_networks_client(self):
        self.compute_networks_client = NetworksClient(self.auth_provider,
                                                      **self.compute_params)

    def set_compute_floating_ips_client(self):
        self.compute_floating_ips_client = FloatingIPsClient(
            self.auth_provider,
            **self.compute_params)

    def set_flavors_client(self):
        self.flavors_client = FlavorsClient(self.auth_provider,
                                            **self.compute_params)

    def set_image_client(self):
        self.image_client = ImagesClient(self.auth_provider,
                                         **self.image_params)

    def set_image_client_v2(self):
        self.image_client_v2 = ImagesClientV2(self.auth_provider,
                                              **self.image_params)

    def set_telemetry_client(self):
        self.telemetry_client = TelemetryClient(self.auth_provider,
                                                **self.telemetry_params)

    def set_container_client(self):
        self.container_client = ContainerClient(self.auth_provider,
                                                **self.object_storage_params)

    def set_object_client(self):
        self.object_client = ObjectClient(self.auth_provider,
                                          **self.object_storage_params)
