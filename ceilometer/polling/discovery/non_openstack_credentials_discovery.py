# Copyright 2014-2015 Red Hat, Inc
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

from oslo_log import log

from ceilometer.polling.discovery.endpoint import EndpointDiscovery

from urllib import parse as urlparse

import requests

LOG = log.getLogger(__name__)


class NonOpenStackCredentialsDiscovery(EndpointDiscovery):
    """Barbican secrets discovery

    Discovery that supplies non-OpenStack credentials for the dynamic
    pollster sub-system. This solution uses the EndpointDiscovery to
    find the Barbican URL where we can retrieve the credentials.
    """

    BARBICAN_URL_GET_PAYLOAD_PATTERN = "/v1/secrets/%s/payload"

    def discover(self, manager, param=None):
        barbican_secret = "No secrets found"
        if not param:
            return [barbican_secret]
        barbican_endpoints = super(NonOpenStackCredentialsDiscovery,
                                   self).discover(manager, "key-manager")
        if not barbican_endpoints:
            LOG.warning("No Barbican endpoints found to execute the"
                        " credentials discovery process to [%s].",
                        param)
            return [barbican_secret]
        else:
            LOG.debug("Barbican endpoint found [%s].", barbican_endpoints)

        barbican_server = next(iter(barbican_endpoints))
        barbican_endpoint = self.BARBICAN_URL_GET_PAYLOAD_PATTERN % param
        babrican_url = urlparse.urljoin(barbican_server, barbican_endpoint)

        LOG.debug("Retrieving secrets from: %s.", babrican_url)
        resp = manager._keystone.session.get(babrican_url, authenticated=True)
        if resp.status_code != requests.codes.ok:
            resp.raise_for_status()

        return [resp._content]
