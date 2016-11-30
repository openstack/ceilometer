# Copyright (C) 2014 eNovance SAS <licensing@enovance.com>
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

import copy

from oslo_log import log
import requests
import six
from six.moves.urllib import parse as urlparse

from ceilometer.i18n import _


LOG = log.getLogger(__name__)


class OpencontrailAPIFailed(Exception):
    pass


class AnalyticsAPIBaseClient(object):
    """Opencontrail Base Statistics REST API Client."""

    def __init__(self, conf, endpoint, data):
        self.conf = conf
        self.endpoint = endpoint
        self.data = data or {}

    def request(self, path, fqdn_uuid, data=None):
        req_data = copy.copy(self.data)
        if data:
            req_data.update(data)

        req_params = self._get_req_params(data=req_data)

        url = urlparse.urljoin(self.endpoint, path + fqdn_uuid)
        self._log_req(url, req_params)
        resp = requests.get(url, **req_params)
        self._log_res(resp)

        if resp.status_code != 200:
            raise OpencontrailAPIFailed(
                _('Opencontrail API returned %(status)s %(reason)s') %
                {'status': resp.status_code, 'reason': resp.reason})

        return resp

    def _get_req_params(self, data=None):
        req_params = {
            'headers': {
                'Accept': 'application/json'
            },
            'data': data,
            'allow_redirects': False,
            'timeout': self.conf.http_timeout,
        }

        return req_params

    def _log_req(self, url, req_params):
        if not self.conf.debug:
            return

        curl_command = ['REQ: curl -i -X GET ']

        params = []
        for name, value in six.iteritems(req_params['data']):
            params.append("%s=%s" % (name, value))

        curl_command.append('"%s?%s" ' % (url, '&'.join(params)))

        for name, value in six.iteritems(req_params['headers']):
            curl_command.append('-H "%s: %s" ' % (name, value))

        LOG.debug(''.join(curl_command))

    def _log_res(self, resp):
        if not self.conf.debug:
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

    def get_vm_statistics(self, fqdn_uuid, data=None):
        """Get statistics of a virtual-machines.

        URL:
            {endpoint}/analytics/uves/virtual-machine/{fqdn_uuid}
        """

        path = '/analytics/uves/virtual-machine/'
        resp = self.request(path, fqdn_uuid, data)

        return resp.json()


class Client(object):
    def __init__(self, conf, endpoint, data=None):
        self.networks = NetworksAPIClient(conf, endpoint, data)
