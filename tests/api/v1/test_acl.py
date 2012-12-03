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

from ceilometer.tests import api as tests_api
from ceilometer.api.v1 import acl


class TestAPIACL(tests_api.TestBase):

    def setUp(self):
        super(TestAPIACL, self).setUp()
        acl.install(self.app, {})

    def test_non_authenticated(self):
        with self.app.test_request_context('/'):
            self.app.preprocess_request()
            self.assertEqual(self.test_app.get().status_code, 401)

    def test_authenticated_wrong_role(self):
        with self.app.test_request_context('/', headers={
                "X-Roles": "Member",
                "X-Tenant-Name": "foobar",
                "X-Tenant-Id": "bc23a9d531064583ace8f67dad60f6bb",
        }):
            self.app.preprocess_request()
            self.assertEqual(self.test_app.get().status_code, 401)

    # FIXME(dhellmann): This test is not properly looking at the tenant
    # info. The status code returned is the expected value, but it
    # is not clear why.
    #
    # def test_authenticated_wrong_tenant(self):
    #     with self.app.test_request_context('/', headers={
    #             "X-Roles": "admin",
    #             "X-Tenant-Name": "foobar",
    #             "X-Tenant-Id": "bc23a9d531064583ace8f67dad60f6bb",
    #     }):
    #         self.app.preprocess_request()
    #         self.assertEqual(self.test_app.get().status_code, 401)

    def test_authenticated(self):
        with self.app.test_request_context('/', headers={
                "X-Roles": "admin",
                "X-Tenant-Name": "admin",
                "X-Tenant-Id": "bc23a9d531064583ace8f67dad60f6bb",
        }):
            self.assertEqual(self.app.preprocess_request(), None)
