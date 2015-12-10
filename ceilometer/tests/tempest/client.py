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

from tempest.common import service_client
from tempest import config
from tempest import manager


CONF = config.CONF


class TelemetryClient(service_client.ServiceClient):

    version = '2'
    uri_prefix = "v2"

    def deserialize(self, body):
        return json.loads(body.replace("\n", ""))

    def serialize(self, body):
        return json.dumps(body)

    def add_sample(self, sample_list, meter_name, meter_unit, volume,
                   sample_type, resource_id, **kwargs):
        sample = {"counter_name": meter_name, "counter_unit": meter_unit,
                  "counter_volume": volume, "counter_type": sample_type,
                  "resource_id": resource_id}
        for key in kwargs:
            sample[key] = kwargs[key]

        sample_list.append(self.serialize(sample))
        return sample_list

    def create_sample(self, meter_name, sample_list):
        uri = "%s/meters/%s" % (self.uri_prefix, meter_name)
        body = self.serialize(sample_list)
        resp, body = self.post(uri, body)
        self.expected_success(200, resp.status)
        body = self.deserialize(body)
        return service_client.ResponseBody(resp, body)

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
        return service_client.ResponseBodyList(resp, body)

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
        return service_client.ResponseBody(resp, body)


class Manager(manager.Manager):

    def __init__(self, credentials=None, service=None):
        super(Manager, self).__init__(credentials, service)
        self._set_telemetry_client()

    def _set_telemetry_client(self):
        if CONF.service_available.ceilometer:
            self.telemetry_client = TelemetryClient(
                self.auth_provider,
                CONF.telemetry.catalog_type,
                CONF.identity.region,
                endpoint_type=CONF.telemetry.endpoint_type,
                disable_ssl_certificate_validation=(
                    CONF.identity.disable_ssl_certificate_validation),
                ca_certs=CONF.identity.ca_certificates_file,
                trace_requests=CONF.debug.trace_requests)
