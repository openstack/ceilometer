# -*- coding: utf-8 -*-
#
# Author: François Rossigneux <francois.rossigneux@inria.fr>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import datetime

from keystoneclient.v2_0 import client as ksclient
import requests

from ceilometer import counter
from ceilometer.central import plugin
from ceilometer.openstack.common import cfg


class KwapiClient(object):
    """Kwapi API client."""

    def __init__(self, url, token=None):
        """Initializes client."""
        self.url = url
        self.token = token

    def iter_probes(self):
        """Returns a list of dicts describing all probes."""
        probes_url = self.url + '/probes/'
        headers = {}
        if self.token is not None:
            headers = {'X-Auth-Token': self.token}
        request = requests.get(probes_url, headers=headers)
        message = request.json
        probes = message['probes']
        for key, value in probes.iteritems():
            probe_dict = value
            probe_dict['id'] = key
            yield probe_dict


class _Base(plugin.CentralPollster):
    """Base class for the Kwapi pollster, derived from CentralPollster."""

    @staticmethod
    def get_kwapi_client():
        """Returns a KwapiClient configured with the proper url and token."""
        keystone = ksclient.Client(username=cfg.CONF.os_username,
                                   password=cfg.CONF.os_password,
                                   tenant_id=cfg.CONF.os_tenant_id,
                                   tenant_name=cfg.CONF.os_tenant_name,
                                   auth_url=cfg.CONF.os_auth_url)
        endpoint = keystone.service_catalog.url_for(service_type='energy',
                                                    endpoint_type='internalURL'
                                                    )
        return KwapiClient(endpoint, keystone.auth_token)

    def iter_probes(self):
        """Iterate over all probes."""
        client = self.get_kwapi_client()
        return client.iter_probes()


class KwapiPollster(_Base):
    """Kwapi pollster derived from the base class."""

    def get_counters(self, manager):
        """Returns all counters."""
        for probe in self.iter_probes():
            yield counter.Counter(
                name='energy',
                type=counter.TYPE_CUMULATIVE,
                unit='kWh',
                volume=probe['kwh'],
                user_id=None,
                project_id=None,
                resource_id=probe['id'],
                timestamp=datetime.datetime.fromtimestamp(
                    probe['timestamp']).isoformat(),
                resource_metadata={}
            )
            yield counter.Counter(
                name='power',
                type=counter.TYPE_GAUGE,
                unit='W',
                volume=probe['w'],
                user_id=None,
                project_id=None,
                resource_id=probe['id'],
                timestamp=datetime.datetime.fromtimestamp(
                    probe['timestamp']).isoformat(),
                resource_metadata={}
            )
