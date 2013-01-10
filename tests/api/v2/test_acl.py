# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
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
"""Test ACL."""

from ceilometer.api import acl
from ceilometer.api import app
from ceilometer.openstack.common import cfg
from .base import FunctionalTest


class TestAPIACL(FunctionalTest):

    def _make_app(self):
        # Save the original app constructor so
        # we can use it in our wrapper
        original_setup_app = app.setup_app

        # Wrap application construction with
        # a function that ensures the AdminAuthHook
        # is provided.
        def setup_app(config, extra_hooks=[]):
            extra_hooks = extra_hooks[:]
            extra_hooks.append(acl.AdminAuthHook())
            return original_setup_app(config, extra_hooks)

        self.stubs.Set(app, 'setup_app', setup_app)
        result = super(TestAPIACL, self)._make_app()
        acl.install(result, cfg.CONF)
        return result

    def test_non_authenticated(self):
        response = self.get_json('/sources', expect_errors=True)
        self.assertEqual(response.status_int, 401)

    def test_authenticated_wrong_role(self):
        response = self.get_json('/sources',
                                 expect_errors=True,
                                 headers={
                "X-Roles": "Member",
                "X-Tenant-Name": "admin",
                "X-Tenant-Id": "bc23a9d531064583ace8f67dad60f6bb",
                })
        self.assertEqual(response.status_int, 401)

    # FIXME(dhellmann): This test is not properly looking at the tenant
    # info. We do not correctly detect the improper tenant. That's
    # really something the keystone middleware would have to do using
    # the incoming token, which we aren't providing.
    #
    # def test_authenticated_wrong_tenant(self):
    #     response = self.get_json('/sources',
    #                              expect_errors=True,
    #                              headers={
    #             "X-Roles": "admin",
    #             "X-Tenant-Name": "achoo",
    #             "X-Tenant-Id": "bc23a9d531064583ace8f67dad60f6bb",
    #             })
    #     self.assertEqual(response.status_int, 401)

    def test_authenticated(self):
        response = self.get_json('/sources',
                                 expect_errors=True,
                                 headers={
                "X-Roles": "admin",
                "X-Tenant-Name": "admin",
                "X-Tenant-Id": "bc23a9d531064583ace8f67dad60f6bb",
                })
        self.assertEqual(response.status_int, 200)
