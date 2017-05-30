#
# Copyright 2013 NEC Corporation.  All rights reserved.
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

import abc

from oslo_log import log
import requests
from requests import auth
import six

from ceilometer.i18n import _


LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class _Base(object):
    """Base class of OpenDaylight REST APIs Clients."""

    @abc.abstractproperty
    def base_url(self):
        """Returns base url for each REST API."""

    def __init__(self, client):
        self.client = client

    def request(self, path, container_name):
        return self.client.request(self.base_url + path, container_name)


class OpenDaylightRESTAPIFailed(Exception):
    pass


class StatisticsAPIClient(_Base):
    """OpenDaylight Statistics REST API Client

    Base URL:
      {endpoint}/statistics/{containerName}
    """

    base_url = '/statistics/%(container_name)s'

    def get_port_statistics(self, container_name):
        """Get port statistics

        URL:
            {Base URL}/port
        """
        return self.request('/port', container_name)

    def get_flow_statistics(self, container_name):
        """Get flow statistics

        URL:
            {Base URL}/flow
        """
        return self.request('/flow', container_name)

    def get_table_statistics(self, container_name):
        """Get table statistics

        URL:
            {Base URL}/table
        """
        return self.request('/table', container_name)


class TopologyAPIClient(_Base):
    """OpenDaylight Topology REST API Client

    Base URL:
      {endpoint}/topology/{containerName}
    """

    base_url = '/topology/%(container_name)s'

    def get_topology(self, container_name):
        """Get topology

        URL:
            {Base URL}
        """
        return self.request('', container_name)

    def get_user_links(self, container_name):
        """Get user links

        URL:
            {Base URL}/userLinks
        """
        return self.request('/userLinks', container_name)


class SwitchManagerAPIClient(_Base):
    """OpenDaylight Switch Manager REST API Client

    Base URL:
      {endpoint}/switchmanager/{containerName}
    """

    base_url = '/switchmanager/%(container_name)s'

    def get_nodes(self, container_name):
        """Get node information

        URL:
            {Base URL}/nodes
        """
        return self.request('/nodes', container_name)


class HostTrackerAPIClient(_Base):
    """OpenDaylight Host Tracker REST API Client

    Base URL:
      {endpoint}/hosttracker/{containerName}
    """

    base_url = '/hosttracker/%(container_name)s'

    def get_active_hosts(self, container_name):
        """Get active hosts information

        URL:
            {Base URL}/hosts/active
        """
        return self.request('/hosts/active', container_name)

    def get_inactive_hosts(self, container_name):
        """Get inactive hosts information

        URL:
            {Base URL}/hosts/inactive
        """
        return self.request('/hosts/inactive', container_name)


class Client(object):

    def __init__(self, conf, endpoint, params):
        self.statistics = StatisticsAPIClient(self)
        self.topology = TopologyAPIClient(self)
        self.switch_manager = SwitchManagerAPIClient(self)
        self.host_tracker = HostTrackerAPIClient(self)

        self._endpoint = endpoint
        self.conf = conf

        self._req_params = self._get_req_params(params)

    def _get_req_params(self, params):
        req_params = {
            'headers': {
                'Accept': 'application/json'
            },
            'timeout': self.conf.http_timeout,
        }

        auth_way = params.get('auth')
        if auth_way in ['basic', 'digest']:
            user = params.get('user')
            password = params.get('password')

            if auth_way == 'basic':
                auth_class = auth.HTTPBasicAuth
            else:
                auth_class = auth.HTTPDigestAuth

            req_params['auth'] = auth_class(user, password)
        return req_params

    def _log_req(self, url):

        curl_command = ['REQ: curl -i -X GET ', '"%s" ' % (url)]

        if 'auth' in self._req_params:
            auth_class = self._req_params['auth']
            if isinstance(auth_class, auth.HTTPBasicAuth):
                curl_command.append('--basic ')
            else:
                curl_command.append('--digest ')

            curl_command.append('--user "%s":"***" ' % auth_class.username)

        for name, value in six.iteritems(self._req_params['headers']):
            curl_command.append('-H "%s: %s" ' % (name, value))

        LOG.debug(''.join(curl_command))

    @staticmethod
    def _log_res(resp):

        dump = ['RES: \n', 'HTTP %.1f %s %s\n' % (resp.raw.version,
                                                  resp.status_code,
                                                  resp.reason)]
        dump.extend('%s: %s\n' % (k, v)
                    for k, v in six.iteritems(resp.headers))
        dump.append('\n')
        if resp.content:
            dump.extend([resp.content, '\n'])

        LOG.debug(''.join(dump))

    def _http_request(self, url):
        if self.conf.debug:
            self._log_req(url)
        resp = requests.get(url, **self._req_params)
        if self.conf.debug:
            self._log_res(resp)
        if resp.status_code // 100 != 2:
            raise OpenDaylightRESTAPIFailed(
                _('OpenDaylight API returned %(status)s %(reason)s') %
                {'status': resp.status_code, 'reason': resp.reason})

        return resp.json()

    def request(self, path, container_name):

        url = self._endpoint + path % {'container_name': container_name}
        return self._http_request(url)
