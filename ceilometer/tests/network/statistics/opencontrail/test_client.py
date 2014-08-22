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

import mock
from oslotest import base

from ceilometer.network.statistics.opencontrail import client


class TestOpencontrailClient(base.BaseTestCase):

    def setUp(self):
        super(TestOpencontrailClient, self).setUp()
        self.client = client.Client('http://127.0.0.1:8143',
                                    'admin', 'admin', None, False)

        self.post_resp = mock.MagicMock()
        self.post = mock.patch('requests.post',
                               return_value=self.post_resp).start()

        self.post_resp.raw.version = 1.1
        self.post_resp.status_code = 302
        self.post_resp.reason = 'Moved'
        self.post_resp.headers = {}
        self.post_resp.cookies = {'connect.sid': 'aaa'}
        self.post_resp.content = 'dummy'

        self.get_resp = mock.MagicMock()
        self.get = mock.patch('requests.get',
                              return_value=self.get_resp).start()
        self.get_resp.raw_version = 1.1
        self.get_resp.status_code = 200
        self.post_resp.content = 'dqs'

    def test_port_statistics(self):
        uuid = 'bbb'
        self.client.networks.get_port_statistics(uuid)

        call_args = self.post.call_args_list[0][0]
        call_kwargs = self.post.call_args_list[0][1]

        expected_url = 'http://127.0.0.1:8143/authenticate'
        self.assertEqual(expected_url, call_args[0])

        data = call_kwargs.get('data')
        expected_data = {'domain': None, 'password': 'admin',
                         'username': 'admin'}
        self.assertEqual(expected_data, data)

        call_args = self.get.call_args_list[0][0]
        call_kwargs = self.get.call_args_list[0][1]

        expected_url = ('http://127.0.0.1:8143/api/tenant/'
                        'networking/virtual-machines/details')
        self.assertEqual(expected_url, call_args[0])

        data = call_kwargs.get('data')
        cookies = call_kwargs.get('cookies')

        expected_data = {'fqnUUID': 'bbb', 'type': 'vn'}
        expected_cookies = {'connect.sid': 'aaa'}
        self.assertEqual(expected_data, data)
        self.assertEqual(expected_cookies, cookies)
