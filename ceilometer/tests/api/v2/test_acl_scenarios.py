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
import json

import testscenarios

from ceilometer.api import acl
from ceilometer.api.controllers import v2 as v2_api
from ceilometer.openstack.common import timeutils
from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.tests.api.v2 import FunctionalTest
from ceilometer.tests import db as tests_db


load_tests = testscenarios.load_tests_apply_scenarios

VALID_TOKEN = '4562138218392831'
VALID_TOKEN2 = '4562138218392832'


class FakeMemcache(object):
    @staticmethod
    def get(key):
        if key == "tokens/%s" % VALID_TOKEN:
            dt = timeutils.utcnow() + datetime.timedelta(minutes=5)
            return json.dumps(({'access': {
                'token': {'id': VALID_TOKEN,
                          'expires': timeutils.isotime(dt)},
                'user': {
                    'id': 'user_id1',
                    'name': 'user_name1',
                    'tenantId': '123i2910',
                    'tenantName': 'mytenant',
                    'roles': [
                        {'name': 'admin'},
                    ]},
            }}, timeutils.isotime(dt)))
        if key == "tokens/%s" % VALID_TOKEN2:
            dt = timeutils.utcnow() + datetime.timedelta(minutes=5)
            return json.dumps(({'access': {
                'token': {'id': VALID_TOKEN2,
                          'expires': timeutils.isotime(dt)},
                'user': {
                    'id': 'user_id2',
                    'name': 'user-good',
                    'tenantId': 'project-good',
                    'tenantName': 'goodies',
                    'roles': [
                        {'name': 'Member'},
                    ]},
            }}, timeutils.isotime(dt)))

    @staticmethod
    def set(key, value, **kwargs):
        pass


class TestAPIACL(FunctionalTest,
                 tests_db.MixinTestsWithBackendScenarios):

    def setUp(self):
        super(TestAPIACL, self).setUp()
        self.environ = {'fake.cache': FakeMemcache()}

        for cnt in [
                sample.Sample(
                    'meter.test',
                    'cumulative',
                    '',
                    1,
                    'user-good',
                    'project-good',
                    'resource-good',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 40),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.sample'},
                    source='test_source'),
                sample.Sample(
                    'meter.mine',
                    'gauge',
                    '',
                    1,
                    'user-fred',
                    'project-good',
                    'resource-56',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 43),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.sample4'},
                    source='test_source')]:
            msg = utils.meter_message_from_counter(
                cnt,
                self.CONF.publisher.metering_secret)
            self.conn.record_metering_data(msg)

    def get_json(self, path, expect_errors=False, headers=None,
                 q=[], **params):
        return super(TestAPIACL, self).get_json(path,
                                                expect_errors=expect_errors,
                                                headers=headers,
                                                q=q,
                                                extra_environ=self.environ,
                                                **params)

    def _make_app(self):
        self.CONF.set_override("cache", "fake.cache", group=acl.OPT_GROUP_NAME)
        return super(TestAPIACL, self)._make_app(enable_acl=True)

    def test_non_authenticated(self):
        response = self.get_json('/meters', expect_errors=True)
        self.assertEqual(401, response.status_int)

    def test_authenticated_wrong_role(self):
        response = self.get_json('/meters',
                                 expect_errors=True,
                                 headers={
                                     "X-Roles": "Member",
                                     "X-Tenant-Name": "admin",
                                     "X-Project-Id":
                                     "bc23a9d531064583ace8f67dad60f6bb",
                                 })
        self.assertEqual(401, response.status_int)

    # FIXME(dhellmann): This test is not properly looking at the tenant
    # info. We do not correctly detect the improper tenant. That's
    # really something the keystone middleware would have to do using
    # the incoming token, which we aren't providing.
    #
    # def test_authenticated_wrong_tenant(self):
    #     response = self.get_json('/meters',
    #                              expect_errors=True,
    #                              headers={
    #             "X-Roles": "admin",
    #             "X-Tenant-Name": "achoo",
    #             "X-Project-Id": "bc23a9d531064583ace8f67dad60f6bb",
    #             })
    #     self.assertEqual(401, response.status_int)

    def test_authenticated(self):
        data = self.get_json('/meters',
                             headers={"X-Auth-Token": VALID_TOKEN,
                                      "X-Roles": "admin",
                                      "X-Tenant-Name": "admin",
                                      "X-Project-Id":
                                      "bc23a9d531064583ace8f67dad60f6bb",
                                      })
        ids = set(r['resource_id'] for r in data)
        self.assertEqual(set(['resource-good', 'resource-56']), ids)

    def test_with_non_admin_missing_project_query(self):
        data = self.get_json('/meters',
                             headers={"X-Roles": "Member",
                                      "X-Auth-Token": VALID_TOKEN2,
                                      "X-Project-Id": "project-good"})
        ids = set(r['resource_id'] for r in data)
        self.assertEqual(set(['resource-good', 'resource-56']), ids)

    def test_with_non_admin(self):
        data = self.get_json('/meters',
                             headers={"X-Roles": "Member",
                                      "X-Auth-Token": VALID_TOKEN2,
                                      "X-Project-Id": "project-good"},
                             q=[{'field': 'project_id',
                                 'value': 'project-good',
                                 }])
        ids = set(r['resource_id'] for r in data)
        self.assertEqual(set(['resource-good', 'resource-56']), ids)

    def test_non_admin_wrong_project(self):
        data = self.get_json('/meters',
                             expect_errors=True,
                             headers={"X-Roles": "Member",
                                      "X-Auth-Token": VALID_TOKEN2,
                                      "X-Project-Id": "project-good"},
                             q=[{'field': 'project_id',
                                 'value': 'project-wrong',
                                 }])
        self.assertEqual(401, data.status_int)

    def test_non_admin_two_projects(self):
        data = self.get_json('/meters',
                             expect_errors=True,
                             headers={"X-Roles": "Member",
                                      "X-Auth-Token": VALID_TOKEN2,
                                      "X-Project-Id": "project-good"},
                             q=[{'field': 'project_id',
                                 'value': 'project-good',
                                 },
                                {'field': 'project_id',
                                 'value': 'project-naughty',
                                 }])
        self.assertEqual(401, data.status_int)

    def test_non_admin_get_events(self):

        # NOTE(herndon): wsme does not handle the  error that is being
        # raised in by requires_admin dues to the decorator ordering. wsme
        # does not play nice with other decorators, and so requires_admin
        # must call wsme.wsexpose, and not the other way arou. The
        # implication is that I can't look at the status code in the
        # return value. Work around is to catch the exception here and
        # verify that the status code is correct.

        try:
            # Intentionally *not* using assertRaises here so I can look
            # at the status code of the exception.
            self.get_json('/event_types', expect_errors=True,
                          headers={"X-Roles": "Member",
                                   "X-Auth-Token": VALID_TOKEN2,
                                   "X-Project-Id": "project-good"})
        except v2_api.ClientSideError as ex:
            self.assertEqual(401, ex.code)
        else:
            self.fail()
