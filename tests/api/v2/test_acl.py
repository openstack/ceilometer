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

import datetime
from oslo.config import cfg

from ceilometer.api import acl
from ceilometer import policy

from .base import FunctionalTest

VALID_TOKEN = '4562138218392831'


class FakeMemcache(object):
    def __init__(self):
        self.set_key = None
        self.set_value = None
        self.token_expiration = None

    def get(self, key):
        if key == "tokens/%s" % VALID_TOKEN:
            dt = datetime.datetime.now() + datetime.timedelta(minutes=5)
            return ({'access': {
                'token': {'id': VALID_TOKEN},
                'user': {
                    'id': 'user_id1',
                    'name': 'user_name1',
                    'tenantId': '123i2910',
                    'tenantName': 'mytenant',
                    'roles': [
                        {'name': 'admin'},
                    ]},
            }}, dt.strftime("%s"))

    def set(self, key, value, time=None):
        self.set_value = value
        self.set_key = key


class TestAPIACL(FunctionalTest):

    def setUp(self):
        super(TestAPIACL, self).setUp()
        self.environ = {'fake.cache': FakeMemcache()}

    def get_json(self, path, expect_errors=False, headers=None,
                 q=[], **params):
        return super(TestAPIACL, self).get_json(path,
                                                expect_errors=expect_errors,
                                                headers=headers,
                                                q=q,
                                                extra_environ=self.environ,
                                                **params)

    def _make_app(self):
        cfg.CONF.set_override("cache", "fake.cache", group=acl.OPT_GROUP_NAME)
        return super(TestAPIACL, self)._make_app(enable_acl=True)

    def test_non_authenticated(self):
        response = self.get_json('/meters', expect_errors=True)
        self.assertEqual(response.status_int, 401)

    def test_authenticated_wrong_role(self):
        response = self.get_json('/meters',
                                 expect_errors=True,
                                 headers={
                                     "X-Roles": "Member",
                                     "X-Tenant-Name": "admin",
                                     "X-Tenant-Id":
                                     "bc23a9d531064583ace8f67dad60f6bb",
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
        response = self.get_json('/meters',
                                 expect_errors=True,
                                 headers={
                                     "X-Auth-Token": VALID_TOKEN,
                                     "X-Roles": "admin",
                                     "X-Tenant-Name": "admin",
                                     "X-Tenant-Id":
                                     "bc23a9d531064583ace8f67dad60f6bb",
                                 })
        self.assertEqual(response.status_int, 200)
