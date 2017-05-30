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
import mock
from oslo_config import fixture as config_fixture
from oslotest import base
from requests import auth as req_auth
import six
from six.moves.urllib import parse as urlparse

from ceilometer.i18n import _
from ceilometer.network.statistics.opendaylight import client
from ceilometer import service as ceilometer_service


class TestClientHTTPBasicAuth(base.BaseTestCase):

    auth_way = 'basic'
    scheme = 'http'

    def setUp(self):
        super(TestClientHTTPBasicAuth, self).setUp()
        conf = ceilometer_service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(config_fixture.Config(conf)).conf
        self.parsed_url = urlparse.urlparse(
            'http://127.0.0.1:8080/controller/nb/v2?container_name=default&'
            'container_name=egg&auth=%s&user=admin&password=admin_pass&'
            'scheme=%s' % (self.auth_way, self.scheme))
        self.params = urlparse.parse_qs(self.parsed_url.query)
        self.endpoint = urlparse.urlunparse(
            urlparse.ParseResult(self.scheme,
                                 self.parsed_url.netloc,
                                 self.parsed_url.path,
                                 None, None, None))
        odl_params = {'auth': self.params.get('auth')[0],
                      'user': self.params.get('user')[0],
                      'password': self.params.get('password')[0]}
        self.client = client.Client(self.CONF, self.endpoint, odl_params)

        self.resp = mock.MagicMock()
        self.get = mock.patch('requests.get',
                              return_value=self.resp).start()

        self.resp.raw.version = 1.1
        self.resp.status_code = 200
        self.resp.reason = 'OK'
        self.resp.headers = {}
        self.resp.content = 'dummy'

    def _test_request(self, method, url):
        data = method('default')

        call_args = self.get.call_args_list[0][0]
        call_kwargs = self.get.call_args_list[0][1]

        # check url
        real_url = url % {'container_name': 'default',
                          'scheme': self.scheme}
        self.assertEqual(real_url, call_args[0])

        # check auth parameters
        auth = call_kwargs.get('auth')
        if self.auth_way == 'digest':
            self.assertIsInstance(auth, req_auth.HTTPDigestAuth)
        else:
            self.assertIsInstance(auth, req_auth.HTTPBasicAuth)
        self.assertEqual('admin', auth.username)
        self.assertEqual('admin_pass', auth.password)

        # check header
        self.assertEqual(
            {'Accept': 'application/json'},
            call_kwargs['headers'])

        # check return value
        self.assertEqual(self.get().json(), data)

    def test_flow_statistics(self):
        self._test_request(
            self.client.statistics.get_flow_statistics,
            '%(scheme)s://127.0.0.1:8080/controller/nb/v2'
            '/statistics/%(container_name)s/flow')

    def test_port_statistics(self):
        self._test_request(
            self.client.statistics.get_port_statistics,
            '%(scheme)s://127.0.0.1:8080/controller/nb/v2'
            '/statistics/%(container_name)s/port')

    def test_table_statistics(self):
        self._test_request(
            self.client.statistics.get_table_statistics,
            '%(scheme)s://127.0.0.1:8080/controller/nb/v2'
            '/statistics/%(container_name)s/table')

    def test_topology(self):
        self._test_request(
            self.client.topology.get_topology,
            '%(scheme)s://127.0.0.1:8080/controller/nb/v2'
            '/topology/%(container_name)s')

    def test_user_links(self):
        self._test_request(
            self.client.topology.get_user_links,
            '%(scheme)s://127.0.0.1:8080/controller/nb/v2'
            '/topology/%(container_name)s/userLinks')

    def test_switch(self):
        self._test_request(
            self.client.switch_manager.get_nodes,
            '%(scheme)s://127.0.0.1:8080/controller/nb/v2'
            '/switchmanager/%(container_name)s/nodes')

    def test_active_hosts(self):
        self._test_request(
            self.client.host_tracker.get_active_hosts,
            '%(scheme)s://127.0.0.1:8080/controller/nb/v2'
            '/hosttracker/%(container_name)s/hosts/active')

    def test_inactive_hosts(self):
        self._test_request(
            self.client.host_tracker.get_inactive_hosts,
            '%(scheme)s://127.0.0.1:8080/controller/nb/v2'
            '/hosttracker/%(container_name)s/hosts/inactive')

    def test_http_error(self):
        self.resp.status_code = 404
        self.resp.reason = 'Not Found'

        try:
            self.client.statistics.get_flow_statistics('default')
            self.fail('')
        except client.OpenDaylightRESTAPIFailed as e:
            self.assertEqual(
                _('OpenDaylight API returned %(status)s %(reason)s') %
                {'status': self.resp.status_code,
                 'reason': self.resp.reason},
                six.text_type(e))

    def test_other_error(self):

        class _Exception(Exception):
            pass

        self.get = mock.patch('requests.get',
                              side_effect=_Exception).start()

        self.assertRaises(_Exception,
                          self.client.statistics.get_flow_statistics,
                          'default')


class TestClientHTTPDigestAuth(TestClientHTTPBasicAuth):

    auth_way = 'digest'


class TestClientHTTPSBasicAuth(TestClientHTTPBasicAuth):

    scheme = 'https'


class TestClientHTTPSDigestAuth(TestClientHTTPDigestAuth):

    scheme = 'https'
