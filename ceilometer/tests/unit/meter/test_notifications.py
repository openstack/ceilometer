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
"""Tests for ceilometer.meter.notifications
"""
import mock
import six
import yaml

from oslo_config import fixture as fixture_config
from oslo_utils import fileutils

from ceilometer.meter import notifications
from ceilometer import service as ceilometer_service
from ceilometer.tests import base as test

NOTIFICATION = {
    'event_type': u'test.create',
    'timestamp': u'2015-06-1909: 19: 35.786893',
    'payload': {u'user_id': u'e1d870e51c7340cb9d555b15cbfcaec2',
                u'resource_id': u'bea70e51c7340cb9d555b15cbfcaec23',
                u'timestamp': u'2015-06-19T09: 19: 35.785330',
                u'message_signature': u'fake_signature1',
                u'resource_metadata': {u'foo': u'bar'},
                u'source': u'30be1fc9a03c4e94ab05c403a8a377f2: openstack',
                u'volume': 1.0,
                u'project_id': u'30be1fc9a03c4e94ab05c403a8a377f2',
                },
    u'_context_tenant': u'30be1fc9a03c4e94ab05c403a8a377f2',
    u'_context_request_id': u'req-da91b4bf-d2b5-43ae-8b66-c7752e72726d',
    u'_context_user': u'e1d870e51c7340cb9d555b15cbfcaec2',
    'message_id': u'939823de-c242-45a2-a399-083f4d6a8c3e',
    'publisher_id': "foo123"
}


class TestMeterDefinition(test.BaseTestCase):

    def test_config_definition(self):
        cfg = dict(name="test",
                   event_type="test.create",
                   type="delta",
                   unit="B",
                   volume="payload.volume",
                   resource_id="payload.resource_id",
                   project_id="payload.project_id")
        handler = notifications.MeterDefinition(cfg)
        self.assertTrue(handler.match_type("test.create"))
        self.assertEqual(1, handler.parse_fields("volume", NOTIFICATION))
        self.assertEqual("bea70e51c7340cb9d555b15cbfcaec23",
                         handler.parse_fields("resource_id", NOTIFICATION))
        self.assertEqual("30be1fc9a03c4e94ab05c403a8a377f2",
                         handler.parse_fields("project_id", NOTIFICATION))

    def test_config_missing_fields(self):
        cfg = dict(name="test", type="delta")
        handler = notifications.MeterDefinition(cfg)
        try:
            handler.match_type("test.create")
        except notifications.MeterDefinitionException as e:
            self.assertEqual("Required field event_type not specified",
                             e.message)

    def test_bad_type_cfg_definition(self):
        cfg = dict(name="test", type="foo")
        try:
            notifications.MeterDefinition(cfg)
        except notifications.MeterDefinitionException as e:
            self.assertEqual("Invalid type foo specified", e.message)


class TestMeterProcessing(test.BaseTestCase):

    def setUp(self):
        super(TestMeterProcessing, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        ceilometer_service.prepare_service([])
        self.handler = notifications.ProcessMeterNotifications(mock.Mock())

    def test_fallback_meter_path(self):
        fall_bak_path = notifications.get_config_file()
        self.assertIn("meter/data/meters.yaml", fall_bak_path)

    def __setup_meter_def_file(self, cfg):
        if six.PY3:
            cfg = cfg.encode('utf-8')
        meter_cfg_file = fileutils.write_to_tempfile(content=cfg,
                                                     prefix="meters",
                                                     suffix="yaml")
        self.CONF.set_override(
            'meter_definitions_cfg_file',
            meter_cfg_file, group='meter')
        cfg = notifications.setup_meters_config()
        return cfg

    def test_multiple_meter(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.create",
                        type="delta",
                             unit="B",
                             volume="payload.volume",
                             resource_id="payload.resource_id",
                             project_id="payload.project_id"),
                        dict(name="test2",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="payload.volume",
                             resource_id="payload.resource_id",
                             project_id="payload.project_id")]})
        self.handler.definitions = notifications.load_definitions(
            self.__setup_meter_def_file(cfg))
        c = list(self.handler.process_notification(NOTIFICATION))
        self.assertEqual(2, len(c))

    def test_unmatched_meter(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.update",
                        type="delta",
                        unit="B",
                        volume="payload.volume",
                        resource_id="payload.resource_id",
                        project_id="payload.project_id")]})
        self.handler.definitions = notifications.load_definitions(
            self.__setup_meter_def_file(cfg))
        c = list(self.handler.process_notification(NOTIFICATION))
        self.assertEqual(0, len(c))

    def test_regex_match_meter(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.*",
                        type="delta",
                        unit="B",
                        volume="payload.volume",
                        resource_id="payload.resource_id",
                        project_id="payload.project_id")]})
        self.handler.definitions = notifications.load_definitions(
            self.__setup_meter_def_file(cfg))
        c = list(self.handler.process_notification(NOTIFICATION))
        self.assertEqual(1, len(c))
