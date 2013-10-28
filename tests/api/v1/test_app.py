# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Julien Danjou
#
# Author: Julien Danjou <julien@danjou.info>
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
"""Test basic ceilometer-api app
"""
import os

from ceilometer.api import acl
from ceilometer.api.v1 import app
from ceilometer.openstack.common import fileutils
from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common import test
from ceilometer import service


class TestApp(test.BaseTestCase):

    def setUp(self):
        super(TestApp, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf

    def test_keystone_middleware_conf(self):
        self.CONF.set_override("auth_protocol", "foottp",
                               group=acl.OPT_GROUP_NAME)
        self.CONF.set_override("auth_version", "v2.0",
                               group=acl.OPT_GROUP_NAME)
        self.CONF.set_override("auth_uri", None,
                               group=acl.OPT_GROUP_NAME)
        api_app = app.make_app(self.CONF, attach_storage=False)
        self.assertTrue(api_app.wsgi_app.auth_uri.startswith('foottp'))

    def test_keystone_middleware_parse_conffile(self):
        content = "[{0}]\nauth_protocol = barttp"\
                  "\nauth_version = v2.0".format(acl.OPT_GROUP_NAME)
        tmpfile = fileutils.write_to_tempfile(content=content,
                                              prefix='ceilometer',
                                              suffix='.conf')
        service.prepare_service(['ceilometer-api',
                                 '--config-file=%s' % tmpfile])
        api_app = app.make_app(self.CONF, attach_storage=False)
        self.assertTrue(api_app.wsgi_app.auth_uri.startswith('barttp'))
        os.unlink(tmpfile)
