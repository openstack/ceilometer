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
from oslo_config import fixture as fixture_config
from oslo_log import log

from ceilometer.api import app
from ceilometer.tests import base


class TestApp(base.BaseTestCase):

    def setUp(self):
        super(TestApp, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        log.register_options(cfg.CONF)

    def test_api_paste_file_not_exist(self):
        self.CONF.set_override('api_paste_config', 'non-existent-file')
        with mock.patch.object(self.CONF, 'find_file') as ff:
            ff.return_value = None
            self.assertRaises(cfg.ConfigFilesNotFoundError, app.load_app)

    @mock.patch('ceilometer.storage.get_connection_from_config',
                mock.MagicMock())
    @mock.patch('pecan.make_app')
    def test_pecan_debug(self, mocked):
        def _check_pecan_debug(g_debug, p_debug, expected, workers=1):
            self.CONF.set_override('debug', g_debug)
            if p_debug is not None:
                self.CONF.set_override('pecan_debug', p_debug, group='api')
            self.CONF.set_override('workers', workers, group='api')
            app.setup_app()
            args, kwargs = mocked.call_args
            self.assertEqual(expected, kwargs.get('debug'))

        _check_pecan_debug(g_debug=False, p_debug=None, expected=False)
        _check_pecan_debug(g_debug=True, p_debug=None, expected=False)
        _check_pecan_debug(g_debug=True, p_debug=False, expected=False)
        _check_pecan_debug(g_debug=False, p_debug=True, expected=True)
        _check_pecan_debug(g_debug=True, p_debug=None, expected=False,
                           workers=5)
        _check_pecan_debug(g_debug=False, p_debug=True, expected=False,
                           workers=5)
