# -*- coding: utf-8 -*-
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

from keystoneauth1 import exceptions
from oslo_config import cfg
from oslo_log import log
import requests
import six

from ceilometer.agent import plugin_base
from ceilometer import keystone_client
from ceilometer import sample


LOG = log.getLogger(__name__)

SERVICE_OPTS = [
    cfg.StrOpt('kwapi',
               default='energy',
               help='Kwapi service type.'),
]

cfg.CONF.register_opts(SERVICE_OPTS, group='service_types')


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
        timeout = cfg.CONF.http_timeout
        request = requests.get(probes_url, headers=headers, timeout=timeout)
        message = request.json()
        probes = message['probes']
        for key, value in six.iteritems(probes):
            probe_dict = value
            probe_dict['id'] = key
            yield probe_dict


class _Base(plugin_base.PollsterBase):
    """Base class for the Kwapi pollster, derived from PollsterBase."""

    @property
    def default_discovery(self):
        return 'endpoint:%s' % cfg.CONF.service_types.kwapi

    @staticmethod
    def get_kwapi_client(ksclient, endpoint):
        """Returns a KwapiClient configured with the proper url and token."""
        return KwapiClient(endpoint, keystone_client.get_auth_token(ksclient))

    CACHE_KEY_PROBE = 'kwapi.probes'

    def _iter_probes(self, ksclient, cache, endpoint):
        """Iterate over all probes."""
        key = '%s-%s' % (endpoint, self.CACHE_KEY_PROBE)
        if key not in cache:
            cache[key] = self._get_probes(ksclient, endpoint)
        return iter(cache[key])

    def _get_probes(self, ksclient, endpoint):
        try:
            client = self.get_kwapi_client(ksclient, endpoint)
        except exceptions.EndpointNotFound:
            LOG.debug("Kwapi endpoint not found")
            return []
        return list(client.iter_probes())


class EnergyPollster(_Base):
    """Measures energy consumption."""
    def get_samples(self, manager, cache, resources):
        """Returns all samples."""
        for endpoint in resources:
            for probe in self._iter_probes(manager.keystone, cache, endpoint):
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
    def get_samples(self, manager, cache, resources):
        """Returns all samples."""
        for endpoint in resources:
            for probe in self._iter_probes(manager.keystone, cache, endpoint):
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
