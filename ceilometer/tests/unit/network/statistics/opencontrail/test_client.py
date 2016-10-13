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

import mock
from oslo_config import fixture as config_fixture
from oslotest import base

from ceilometer.network.statistics.opencontrail import client
from ceilometer import service as ceilometer_service


class TestOpencontrailClient(base.BaseTestCase):

    def setUp(self):
        super(TestOpencontrailClient, self).setUp()
        conf = ceilometer_service.prepare_service(argv=[], config_files=[])
        self.CONF = self.useFixture(config_fixture.Config(conf)).conf
        self.client = client.Client(self.CONF, 'http://127.0.0.1:8081',
                                    {'arg1': 'aaa'})

        self.get_resp = mock.MagicMock()
        self.get = mock.patch('requests.get',
                              return_value=self.get_resp).start()
        self.get_resp.raw.version = 1.1
        self.get_resp.status_code = 200
        self.get_resp.reason = 'OK'
        self.get_resp.content = ''

    def test_vm_statistics(self):
        self.client.networks.get_vm_statistics('bbb')

        call_args = self.get.call_args_list[0][0]
        call_kwargs = self.get.call_args_list[0][1]

        expected_url = ('http://127.0.0.1:8081/analytics/'
                        'uves/virtual-machine/bbb')
        self.assertEqual(expected_url, call_args[0])

        data = call_kwargs.get('data')

        expected_data = {'arg1': 'aaa'}
        self.assertEqual(expected_data, data)

    def test_vm_statistics_params(self):
        self.client.networks.get_vm_statistics('bbb',
                                               {'resource': 'fip_stats_list',
                                                'virtual_network': 'ccc'})

        call_args = self.get.call_args_list[0][0]
        call_kwargs = self.get.call_args_list[0][1]

        expected_url = ('http://127.0.0.1:8081/analytics/'
                        'uves/virtual-machine/bbb')
        self.assertEqual(expected_url, call_args[0])

        data = call_kwargs.get('data')

        expected_data = {'arg1': 'aaa',
                         'resource': 'fip_stats_list',
                         'virtual_network': 'ccc'}
        self.assertEqual(expected_data, data)
