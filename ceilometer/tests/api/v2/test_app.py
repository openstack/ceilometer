# -*- encoding: utf-8 -*-
#
# Copyright 2013 IBM Corp.
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
import json
import os

import mock
import wsme

from ceilometer.api import acl
from ceilometer.api import app
from ceilometer.openstack.common import fileutils
from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common import gettextutils
from ceilometer import service
from ceilometer.tests.api.v2 import FunctionalTest
from ceilometer.tests import base
from ceilometer.tests import db as tests_db


class TestApp(base.BaseTestCase):

    def setUp(self):
        super(TestApp, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf

    def test_keystone_middleware_conf(self):
        self.CONF.set_override("auth_protocol", "foottp",
                               group=acl.OPT_GROUP_NAME)
        self.CONF.set_override("auth_version", "v2.0",
                               group=acl.OPT_GROUP_NAME)
        self.CONF.set_override("pipeline_cfg_file",
                               self.path_get("etc/ceilometer/pipeline.yaml"))
        self.CONF.set_override('connection', "log://", group="database")
        self.CONF.set_override("auth_uri", None, group=acl.OPT_GROUP_NAME)

        api_app = app.setup_app()
        self.assertTrue(api_app.auth_uri.startswith('foottp'))

    def test_keystone_middleware_parse_conffile(self):
        pipeline_conf = self.path_get("etc/ceilometer/pipeline.yaml")
        content = "[DEFAULT]\n"\
                  "pipeline_cfg_file = {0}\n"\
                  "[{1}]\n"\
                  "auth_protocol = barttp\n"\
                  "auth_version = v2.0\n".format(pipeline_conf,
                                                 acl.OPT_GROUP_NAME)

        tmpfile = fileutils.write_to_tempfile(content=content,
                                              prefix='ceilometer',
                                              suffix='.conf')
        service.prepare_service(['ceilometer-api',
                                 '--config-file=%s' % tmpfile])
        self.CONF.set_override('connection', "log://", group="database")
        api_app = app.setup_app()
        self.assertTrue(api_app.auth_uri.startswith('barttp'))
        os.unlink(tmpfile)


class TestPecanApp(FunctionalTest):
    database_connection = tests_db.MongoDBFakeConnectionUrl()

    def test_pecan_extension_guessing_unset(self):
        # check Pecan does not assume .jpg is an extension
        response = self.app.get(self.PATH_PREFIX + '/meters/meter.jpg')
        self.assertEqual(response.content_type, 'application/json')


class TestApiMiddleware(FunctionalTest):

    # This doesn't really matter
    database_connection = tests_db.MongoDBFakeConnectionUrl()

    no_lang_translated_error = 'No lang translated error'
    en_US_translated_error = 'en-US translated error'

    def _fake_translate(self, message, user_locale):
        if user_locale is None:
            return self.no_lang_translated_error
        else:
            return self.en_US_translated_error

    def test_json_parsable_error_middleware_404(self):
        response = self.get_json('/invalid_path',
                                 expect_errors=True,
                                 headers={"Accept":
                                          "application/json"}
                                 )
        self.assertEqual(response.status_int, 404)
        self.assertEqual(response.content_type, "application/json")
        self.assertTrue(response.json['error_message'])
        response = self.get_json('/invalid_path',
                                 expect_errors=True,
                                 headers={"Accept":
                                          "application/json,application/xml"}
                                 )
        self.assertEqual(response.status_int, 404)
        self.assertEqual(response.content_type, "application/json")
        self.assertTrue(response.json['error_message'])
        response = self.get_json('/invalid_path',
                                 expect_errors=True,
                                 headers={"Accept":
                                          "application/xml;q=0.8, \
                                          application/json"}
                                 )
        self.assertEqual(response.status_int, 404)
        self.assertEqual(response.content_type, "application/json")
        self.assertTrue(response.json['error_message'])
        response = self.get_json('/invalid_path',
                                 expect_errors=True
                                 )
        self.assertEqual(response.status_int, 404)
        self.assertEqual(response.content_type, "application/json")
        self.assertTrue(response.json['error_message'])
        response = self.get_json('/invalid_path',
                                 expect_errors=True,
                                 headers={"Accept":
                                          "text/html,*/*"}
                                 )
        self.assertEqual(response.status_int, 404)
        self.assertEqual(response.content_type, "application/json")
        self.assertTrue(response.json['error_message'])

    def test_json_parsable_error_middleware_translation_400(self):
        # Ensure translated messages get placed properly into json faults
        with mock.patch.object(gettextutils, 'translate',
                               side_effect=self._fake_translate):
            response = self.post_json('/alarms', params={'name': 'foobar',
                                                         'type': 'threshold'},
                                      expect_errors=True,
                                      headers={"Accept":
                                               "application/json"}
                                      )
        self.assertEqual(response.status_int, 400)
        self.assertEqual(response.content_type, "application/json")
        self.assertTrue(response.json['error_message'])
        self.assertEqual(response.json['error_message']['faultstring'],
                         self.no_lang_translated_error)

    def test_xml_parsable_error_middleware_404(self):
        response = self.get_json('/invalid_path',
                                 expect_errors=True,
                                 headers={"Accept":
                                          "application/xml,*/*"}
                                 )
        self.assertEqual(response.status_int, 404)
        self.assertEqual(response.content_type, "application/xml")
        self.assertEqual(response.xml.tag, 'error_message')
        response = self.get_json('/invalid_path',
                                 expect_errors=True,
                                 headers={"Accept":
                                          "application/json;q=0.8 \
                                          ,application/xml"}
                                 )
        self.assertEqual(response.status_int, 404)
        self.assertEqual(response.content_type, "application/xml")
        self.assertEqual(response.xml.tag, 'error_message')

    def test_xml_parsable_error_middleware_translation_400(self):
        # Ensure translated messages get placed properly into xml faults
        with mock.patch.object(gettextutils, 'translate',
                               side_effect=self._fake_translate):
            response = self.post_json('/alarms', params={'name': 'foobar',
                                                         'type': 'threshold'},
                                      expect_errors=True,
                                      headers={"Accept":
                                               "application/xml,*/*"}
                                      )
        self.assertEqual(response.status_int, 400)
        self.assertEqual(response.content_type, "application/xml")
        self.assertEqual(response.xml.tag, 'error_message')
        fault = response.xml.findall('./error/faultstring')
        for fault_string in fault:
            self.assertEqual(fault_string.text, self.no_lang_translated_error)

    def test_best_match_language(self):
        # Ensure that we are actually invoking language negotiation
        with mock.patch.object(gettextutils, 'translate',
                               side_effect=self._fake_translate):
            response = self.post_json('/alarms', params={'name': 'foobar',
                                                         'type': 'threshold'},
                                      expect_errors=True,
                                      headers={"Accept":
                                               "application/xml,*/*",
                                               "Accept-Language":
                                               "en-US"}
                                      )

        self.assertEqual(response.status_int, 400)
        self.assertEqual(response.content_type, "application/xml")
        self.assertEqual(response.xml.tag, 'error_message')
        fault = response.xml.findall('./error/faultstring')
        for fault_string in fault:
            self.assertEqual(fault_string.text, self.en_US_translated_error)

    def test_translated_then_untranslated_error(self):
        resp = self.get_json('/alarms/alarm-id-3', expect_errors=True)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(json.loads(resp.body)['error_message']
                         ['faultstring'], "Alarm alarm-id-3 Not Found")

        with mock.patch('ceilometer.api.controllers.v2.EntityNotFound') \
                as CustomErrorClass:
            CustomErrorClass.return_value = wsme.exc.ClientSideError(
                "untranslated_error", status_code=404)
            resp = self.get_json('/alarms/alarm-id-5', expect_errors=True)

        self.assertEqual(resp.status_code, 404)
        self.assertEqual(json.loads(resp.body)['error_message']
                         ['faultstring'], "untranslated_error")
