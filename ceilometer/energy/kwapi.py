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

from keystoneclient import exceptions
from oslo.config import cfg
import requests

from ceilometer.central import plugin
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer import sample

LOG = log.getLogger(__name__)


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
        message = request.json()
        probes = message['probes']
        for key, value in probes.iteritems():
            probe_dict = value
            probe_dict['id'] = key
            yield probe_dict


class _Base(plugin.CentralPollster):
    """Base class for the Kwapi pollster, derived from CentralPollster."""

    @staticmethod
    def get_kwapi_client(ksclient):
        """Returns a KwapiClient configured with the proper url and token."""
        endpoint = ksclient.service_catalog.url_for(
            service_type='energy',
            endpoint_type=cfg.CONF.service_credentials.os_endpoint_type)
        return KwapiClient(endpoint, ksclient.auth_token)

    CACHE_KEY_PROBE = 'kwapi.probes'

    def _iter_probes(self, ksclient, cache):
        """Iterate over all probes."""
        if self.CACHE_KEY_PROBE not in cache:
            cache[self.CACHE_KEY_PROBE] = self._get_probes(ksclient)
        return iter(cache[self.CACHE_KEY_PROBE])

    def _get_probes(self, ksclient):
        try:
            client = self.get_kwapi_client(ksclient)
        except exceptions.EndpointNotFound:
            LOG.debug(_("Kwapi endpoint not found"))
            return []
        return list(client.iter_probes())


class EnergyPollster(_Base):
    """Measures energy consumption."""

    def get_samples(self, manager, cache, resources=[]):
        """Returns all samples."""
        for probe in self._iter_probes(manager.keystone, cache):
            yield sample.Sample(
                name='energy',
                type=sample.TYPE_CUMULATIVE,
                unit='kWh',
                volume=probe['kwh'],
                user_id=None,
                project_id=None,
                resource_id=probe['id'],
                timestamp=datetime.datetime.fromtimestamp(
                    probe['timestamp']).isoformat(),
                resource_metadata={}
            )


class PowerPollster(_Base):
    """Measures power consumption."""

    def get_samples(self, manager, cache, resources=[]):
        """Returns all samples."""
        for probe in self._iter_probes(manager.keystone, cache):
            yield sample.Sample(
                name='power',
                type=sample.TYPE_GAUGE,
                unit='W',
                volume=probe['w'],
                user_id=None,
                project_id=None,
                resource_id=probe['id'],
                timestamp=datetime.datetime.fromtimestamp(
                    probe['timestamp']).isoformat(),
                resource_metadata={}
            )
