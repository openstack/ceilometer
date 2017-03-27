# Copyright 2014 IBM Corp.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock
from oslo_config import cfg

from ceilometer.api import app
from ceilometer import service
from ceilometer.tests import base


class TestApp(base.BaseTestCase):

    def setUp(self):
        super(TestApp, self).setUp()
        self.CONF = service.prepare_service([], [])

    def test_api_paste_file_not_exist(self):
        self.CONF.set_override('api_paste_config', 'non-existent-file')
        with mock.patch.object(self.CONF, 'find_file') as ff:
            ff.return_value = None
            self.assertRaises(cfg.ConfigFilesNotFoundError, app.load_app,
                              self.CONF)
