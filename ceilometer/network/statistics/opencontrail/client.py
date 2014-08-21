# Copyright (C) 2014 eNovance SAS <licensing@enovance.com>
#
# Author: Sylvain Afchain <sylvain.afchain@enovance.com>
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

from oslo.config import cfg
import requests
import six
from six.moves.urllib import parse as urlparse

from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log


CONF = cfg.CONF


LOG = log.getLogger(__name__)


class OpencontrailAPIFailed(Exception):
    pass


class AnalyticsAPIBaseClient(object):
    """Opencontrail Base Statistics REST API Client."""

    def __init__(self, endpoint, username, password, domain, verify_ssl=True):
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.domain = domain
        self.verify_ssl = verify_ssl
        self.sid = None

    def authenticate(self):
        path = '/authenticate'
        data = {'username': self.username,
                'password': self.password,
                'domain': self.domain}

        req_params = self._get_req_params(data=data)
        url = urlparse.urljoin(self.endpoint, path)
        resp = requests.post(url, **req_params)
        if resp.status_code != 302:
            raise OpencontrailAPIFailed(
                _('Opencontrail API returned %(status)s %(reason)s') %
                {'status': resp.status_code, 'reason': resp.reason})
        self.sid = resp.cookies['connect.sid']

    def request(self, path, fqdn_uuid, data, retry=True):
        if not self.sid:
            self.authenticate()

        if not data:
            data = {'fqnUUID': fqdn_uuid}
        else:
            data['fqnUUID'] = fqdn_uuid

        req_params = self._get_req_params(data=data,
                                          cookies={'connect.sid': self.sid})

        url = urlparse.urljoin(self.endpoint, path)
        self._log_req(url, req_params)
        resp = requests.get(url, **req_params)
        self._log_res(resp)

        # it seems that the sid token has to be renewed
        if resp.status_code == 302:
            self.sid = 0
            if retry:
                return self.request(path, fqdn_uuid, data,
                                    retry=False)

        if resp.status_code != 200:
            raise OpencontrailAPIFailed(
                _('Opencontrail API returned %(status)s %(reason)s') %
                {'status': resp.status_code, 'reason': resp.reason})

        return resp

    def _get_req_params(self, params=None, data=None, cookies=None):
        req_params = {
            'headers': {
                'Accept': 'application/json'
            },
            'data': data,
            'verify': self.verify_ssl,
            'allow_redirects': False,
            'cookies': cookies
        }

        return req_params

    @staticmethod
    def _log_req(url, req_params):
        if not CONF.debug:
            return

        curl_command = ['REQ: curl -i -X GET ']

        params = []
        for name, value in six.iteritems(req_params['data']):
            params.append("%s=%s" % (name, value))

        curl_command.append('"%s?%s" ' % (url, '&'.join(params)))

        for name, value in six.iteritems(req_params['headers']):
            curl_command.append('-H "%s: %s" ' % (name, value))

        LOG.debug(''.join(curl_command))

    @staticmethod
    def _log_res(resp):
        if not CONF.debug:
            return

        dump = ['RES: \n', 'HTTP %.1f %s %s\n' % (resp.raw.version,
                                                  resp.status_code,
                                                  resp.reason)]
        dump.extend('%s: %s\n' % (k, v)
                    for k, v in six.iteritems(resp.headers))
        dump.append('\n')
        if resp.content:
            dump.extend([resp.content, '\n'])

        LOG.debug(''.join(dump))


class NetworksAPIClient(AnalyticsAPIBaseClient):
    """Opencontrail Statistics REST API Client."""

    def get_port_statistics(self, fqdn_uuid):
        """Get port statistics of a network

        URL:
            /tenant/networking/virtual-machines/details
        PARAMS:
            fqdnUUID=fqdn_uuid
            type=vn
        """

        path = '/api/tenant/networking/virtual-machines/details'
        resp = self.request(path, fqdn_uuid, {'type': 'vn'})

        return resp.json()


class Client(object):

    def __init__(self, endpoint, username, password, domain, verify_ssl=True):
        self.networks = NetworksAPIClient(endpoint, username, password,
                                          domain, verify_ssl)
