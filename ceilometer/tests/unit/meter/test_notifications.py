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
import copy
import mock
import six
import yaml

from oslo_config import fixture as fixture_config
from oslo_utils import fileutils
from oslotest import mockpatch

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

MIDDLEWARE_EVENT = {
    u'_context_request_id': u'req-a8bfa89b-d28b-4b95-9e4b-7d7875275650',
    u'_context_quota_class': None,
    u'event_type': u'objectstore.http.request',
    u'_context_service_catalog': [],
    u'_context_auth_token': None,
    u'_context_user_id': None,
    u'priority': u'INFO',
    u'_context_is_admin': True,
    u'_context_user': None,
    u'publisher_id': u'ceilometermiddleware',
    u'message_id': u'6eccedba-120e-4db8-9735-2ad5f061e5ee',
    u'_context_remote_address': None,
    u'_context_roles': [],
    u'timestamp': u'2013-07-29 06:51:34.474815',
    u'_context_timestamp': u'2013-07-29T06:51:34.348091',
    u'_unique_id': u'0ee26117077648e18d88ac76e28a72e2',
    u'_context_project_name': None,
    u'_context_read_deleted': u'no',
    u'_context_tenant': None,
    u'_context_instance_lock_checked': False,
    u'_context_project_id': None,
    u'_context_user_name': None,
    u'payload': {
        'typeURI': 'http: //schemas.dmtf.org/cloud/audit/1.0/event',
        'eventTime': '2015-01-30T16: 38: 43.233621',
        'target': {
            'action': 'get',
            'typeURI': 'service/storage/object',
            'id': 'account',
            'metadata': {
                'path': '/1.0/CUSTOM_account/container/obj',
                'version': '1.0',
                'container': 'container',
                'object': 'obj'
            }
        },
        'observer': {
            'id': 'target'
        },
        'eventType': 'activity',
        'measurements': [
            {
                'metric': {
                    'metricId': 'openstack: uuid',
                    'name': 'storage.objects.outgoing.bytes',
                    'unit': 'B'
                },
                'result': 28
            },
            {
                'metric': {
                    'metricId': 'openstack: uuid2',
                    'name': 'storage.objects.incoming.bytes',
                    'unit': 'B'
                },
                'result': 1
            }
        ],
        'initiator': {
            'typeURI': 'service/security/account/user',
            'project_id': None,
            'id': 'openstack: 288f6260-bf37-4737-a178-5038c84ba244'
        },
        'action': 'read',
        'outcome': 'success',
        'id': 'openstack: 69972bb6-14dd-46e4-bdaf-3148014363dc'
    }
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
        self.useFixture(mockpatch.PatchObject(self.CONF,
                        'find_file', return_value=None))
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

    def test_jsonpath_values_parsed(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.create",
                        type="delta",
                             unit="B",
                             volume="payload.volume",
                             resource_id="payload.resource_id",
                             project_id="payload.project_id")]})
        self.handler.definitions = notifications.load_definitions(
            self.__setup_meter_def_file(cfg))
        c = list(self.handler.process_notification(NOTIFICATION))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        self.assertEqual('test1', s1['name'])
        self.assertEqual(1.0, s1['volume'])
        self.assertEqual('bea70e51c7340cb9d555b15cbfcaec23', s1['resource_id'])
        self.assertEqual('30be1fc9a03c4e94ab05c403a8a377f2', s1['project_id'])

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
        s1 = c[0].as_dict()
        self.assertEqual('test2', s1['name'])
        s2 = c[1].as_dict()
        self.assertEqual('test1', s2['name'])

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

    def test_multi_match_event_meter(self):
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

    def test_multi_meter_payload(self):
        cfg = yaml.dump(
            {'metric': [dict(name="payload.measurements.[*].metric.[*].name",
                        event_type="objectstore.http.request",
                        type="delta",
                        unit="payload.measurements.[*].metric.[*].unit",
                        volume="payload.measurements.[*].result",
                        resource_id="payload.target_id",
                        project_id="payload.initiator.project_id",
                        multi="name")]})
        self.handler.definitions = notifications.load_definitions(
            self.__setup_meter_def_file(cfg))
        c = list(self.handler.process_notification(MIDDLEWARE_EVENT))
        self.assertEqual(2, len(c))
        s1 = c[0].as_dict()
        self.assertEqual('storage.objects.outgoing.bytes', s1['name'])
        self.assertEqual(28, s1['volume'])
        self.assertEqual('B', s1['unit'])
        s2 = c[1].as_dict()
        self.assertEqual('storage.objects.incoming.bytes', s2['name'])
        self.assertEqual(1, s2['volume'])
        self.assertEqual('B', s2['unit'])

    def test_multi_meter_payload_single(self):
        event = copy.deepcopy(MIDDLEWARE_EVENT)
        del event['payload']['measurements'][1]
        cfg = yaml.dump(
            {'metric': [dict(name="payload.measurements.[*].metric.[*].name",
                        event_type="objectstore.http.request",
                        type="delta",
                        unit="payload.measurements.[*].metric.[*].unit",
                        volume="payload.measurements.[*].result",
                        resource_id="payload.target_id",
                        project_id="payload.initiator.project_id",
                        multi="name")]})
        self.handler.definitions = notifications.load_definitions(
            self.__setup_meter_def_file(cfg))
        c = list(self.handler.process_notification(event))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        self.assertEqual('storage.objects.outgoing.bytes', s1['name'])
        self.assertEqual(28, s1['volume'])
        self.assertEqual('B', s1['unit'])

    def test_multi_meter_payload_none(self):
        event = copy.deepcopy(MIDDLEWARE_EVENT)
        del event['payload']['measurements']
        cfg = yaml.dump(
            {'metric': [dict(name="payload.measurements.[*].metric.[*].name",
                        event_type="objectstore.http.request",
                        type="delta",
                        unit="payload.measurements.[*].metric.[*].unit",
                        volume="payload.measurements.[*].result",
                        resource_id="payload.target_id",
                        project_id="payload.initiator.project_id",
                        multi="name")]})
        self.handler.definitions = notifications.load_definitions(
            self.__setup_meter_def_file(cfg))
        c = list(self.handler.process_notification(event))
        self.assertEqual(0, len(c))

    @mock.patch('ceilometer.meter.notifications.LOG')
    def test_multi_meter_payload_invalid_missing(self, LOG):
        event = copy.deepcopy(MIDDLEWARE_EVENT)
        del event['payload']['measurements'][0]['result']
        del event['payload']['measurements'][1]['result']
        cfg = yaml.dump(
            {'metric': [dict(name="payload.measurements.[*].metric.[*].name",
                        event_type="objectstore.http.request",
                        type="delta",
                        unit="payload.measurements.[*].metric.[*].unit",
                        volume="payload.measurements.[*].result",
                        resource_id="payload.target_id",
                        project_id="payload.initiator.project_id",
                        multi=["name", "unit", "volume"])]})
        self.handler.definitions = notifications.load_definitions(
            self.__setup_meter_def_file(cfg))
        c = list(self.handler.process_notification(event))
        self.assertEqual(0, len(c))
        LOG.warning.assert_called_with('Could not find %s values', 'volume')

    @mock.patch('ceilometer.meter.notifications.LOG')
    def test_multi_meter_payload_invalid_short(self, LOG):
        event = copy.deepcopy(MIDDLEWARE_EVENT)
        del event['payload']['measurements'][0]['result']
        cfg = yaml.dump(
            {'metric': [dict(name="payload.measurements.[*].metric.[*].name",
                        event_type="objectstore.http.request",
                        type="delta",
                        unit="payload.measurements.[*].metric.[*].unit",
                        volume="payload.measurements.[*].result",
                        resource_id="payload.target_id",
                        project_id="payload.initiator.project_id",
                        multi=["name", "unit", "volume"])]})
        self.handler.definitions = notifications.load_definitions(
            self.__setup_meter_def_file(cfg))
        c = list(self.handler.process_notification(event))
        self.assertEqual(0, len(c))
        LOG.warning.assert_called_with('Not all fetched meters contain "%s" '
                                       'field', 'volume')
