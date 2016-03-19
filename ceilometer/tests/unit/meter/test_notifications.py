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
import os
import six
import yaml

from oslo_config import fixture as fixture_config
from oslo_utils import encodeutils
from oslo_utils import fileutils

import ceilometer
from ceilometer import declarative
from ceilometer.meter import notifications
from ceilometer import service as ceilometer_service
from ceilometer.tests import base as test

NOTIFICATION = {
    'event_type': u'test.create',
    'timestamp': u'2015-06-1909: 19: 35.786893',
    'payload': {u'user_id': u'e1d870e51c7340cb9d555b15cbfcaec2',
                u'resource_id': u'bea70e51c7340cb9d555b15cbfcaec23',
                u'timestamp': u'2015-06-19T09:19:35.785330',
                u'created_at': u'2015-06-19T09:25:35.785330',
                u'launched_at': u'2015-06-19T09:25:40.785330',
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

FULL_MULTI_MSG = {
    u'_context_domain': None,
    u'_context_request_id': u'req-da91b4bf-d2b5-43ae-8b66-c7752e72726d',
    'event_type': u'full.sample',
    'timestamp': u'2015-06-1909: 19: 35.786893',
    u'_context_auth_token': None,
    u'_context_read_only': False,
    'payload': [{
                u'counter_name': u'instance1',
                u'user_id': u'user1',
                u'resource_id': u'res1',
                u'counter_unit': u'ns',
                u'counter_volume': 28.0,
                u'project_id': u'proj1',
                u'counter_type': u'gauge'
                },
                {
                u'counter_name': u'instance2',
                u'user_id': u'user2',
                u'resource_id': u'res2',
                u'counter_unit': u'%',
                u'counter_volume': 1.0,
                u'project_id': u'proj2',
                u'counter_type': u'delta'
                }],
    u'_context_resource_uuid': None,
    u'_context_user_identity': u'fake_user_identity---',
    u'_context_show_deleted': False,
    u'_context_tenant': u'30be1fc9a03c4e94ab05c403a8a377f2',
    'priority': 'info',
    u'_context_is_admin': True,
    u'_context_project_domain': None,
    u'_context_user': u'e1d870e51c7340cb9d555b15cbfcaec2',
    u'_context_user_domain': None,
    'publisher_id': u'ceilometer.api',
    'message_id': u'939823de-c242-45a2-a399-083f4d6a8c3e'
}

METRICS_UPDATE = {
    u'_context_request_id': u'req-a8bfa89b-d28b-4b95-9e4b-7d7875275650',
    u'_context_quota_class': None,
    u'event_type': u'compute.metrics.update',
    u'_context_service_catalog': [],
    u'_context_auth_token': None,
    u'_context_user_id': None,
    u'payload': {
        u'metrics': [
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.frequency', 'value': 1600,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.user.time', 'value': 17421440000000,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.kernel.time', 'value': 7852600000000,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.idle.time', 'value': 1307374400000000,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.iowait.time', 'value': 11697470000000,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.user.percent', 'value': 0.012959045637294348,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.kernel.percent', 'value': 0.005841204961898534,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.idle.percent', 'value': 0.9724985141658965,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.iowait.percent', 'value': 0.008701235234910634,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': u'2013-07-29T06:51:34.472416',
             'name': 'cpu.percent', 'value': 0.027501485834103515,
             'source': 'libvirt.LibvirtDriver'}],
        u'nodename': u'tianst.sh.intel.com',
        u'host': u'tianst',
        u'host_id': u'10.0.1.1'},
    u'priority': u'INFO',
    u'_context_is_admin': True,
    u'_context_user': None,
    u'publisher_id': u'compute.tianst.sh.intel.com',
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
    u'_context_user_name': None
}


class TestMeterDefinition(test.BaseTestCase):

    def test_config_definition(self):
        cfg = dict(name="test",
                   event_type="test.create",
                   type="delta",
                   unit="B",
                   volume="$.payload.volume",
                   resource_id="$.payload.resource_id",
                   project_id="$.payload.project_id")
        handler = notifications.MeterDefinition(cfg, mock.Mock())
        self.assertTrue(handler.match_type("test.create"))
        sample = list(handler.to_samples(NOTIFICATION))[0]
        self.assertEqual(1.0, sample["volume"])
        self.assertEqual("bea70e51c7340cb9d555b15cbfcaec23",
                         sample["resource_id"])
        self.assertEqual("30be1fc9a03c4e94ab05c403a8a377f2",
                         sample["project_id"])

    def test_config_required_missing_fields(self):
        cfg = dict()
        try:
            notifications.MeterDefinition(cfg, mock.Mock())
        except declarative.DefinitionException as e:
            self.assertEqual("Required fields ['name', 'type', 'event_type',"
                             " 'unit', 'volume', 'resource_id']"
                             " not specified",
                             encodeutils.exception_to_unicode(e))

    def test_bad_type_cfg_definition(self):
        cfg = dict(name="test", type="foo", event_type="bar.create",
                   unit="foo", volume="bar",
                   resource_id="bea70e51c7340cb9d555b15cbfcaec23")
        try:
            notifications.MeterDefinition(cfg, mock.Mock())
        except declarative.DefinitionException as e:
            self.assertEqual("Invalid type foo specified",
                             encodeutils.exception_to_unicode(e))


class TestMeterProcessing(test.BaseTestCase):

    def setUp(self):
        super(TestMeterProcessing, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        ceilometer_service.prepare_service(argv=[], config_files=[])
        self.handler = notifications.ProcessMeterNotifications(mock.Mock())

    def test_fallback_meter_path(self):
        self.CONF.set_override('meter_definitions_cfg_file',
                               '/not/existing/path', group='meter')
        with mock.patch('ceilometer.declarative.open',
                        mock.mock_open(read_data='---\nmetric: []'),
                        create=True) as mock_open:
            self.handler._load_definitions()
            if six.PY3:
                path = os.path.dirname(ceilometer.__file__)
            else:
                path = "ceilometer"
            mock_open.assert_called_with(path + "/meter/data/meters.yaml")

    def _load_meter_def_file(self, cfg):
        if six.PY3:
            cfg = cfg.encode('utf-8')
        meter_cfg_file = fileutils.write_to_tempfile(content=cfg,
                                                     prefix="meters",
                                                     suffix="yaml")
        self.CONF.set_override('meter_definitions_cfg_file',
                               meter_cfg_file, group='meter')
        self.handler.definitions = self.handler._load_definitions()

    @mock.patch('ceilometer.meter.notifications.LOG')
    def test_bad_meter_definition_skip(self, LOG):
        cfg = yaml.dump(
            {'metric': [dict(name="good_test_1",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id"),
                        dict(name="bad_test_2", type="bad_type",
                             event_type="bar.create",
                             unit="foo", volume="bar",
                             resource_id="bea70e51c7340cb9d555b15cbfcaec23"),
                        dict(name="good_test_3",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id")]})
        self._load_meter_def_file(cfg)
        self.assertEqual(2, len(self.handler.definitions))
        LOG.error.assert_called_with(
            "Error loading meter definition : "
            "Invalid type bad_type specified")

    def test_jsonpath_values_parsed(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.create",
                        type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id")]})
        self._load_meter_def_file(cfg)
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
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id"),
                        dict(name="test2",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id")]})
        self._load_meter_def_file(cfg)
        data = list(self.handler.process_notification(NOTIFICATION))
        self.assertEqual(2, len(data))
        expected_names = ['test1', 'test2']
        for s in data:
            self.assertIn(s.as_dict()['name'], expected_names)

    def test_unmatched_meter(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.update",
                        type="delta",
                        unit="B",
                        volume="$.payload.volume",
                        resource_id="$.payload.resource_id",
                        project_id="$.payload.project_id")]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(NOTIFICATION))
        self.assertEqual(0, len(c))

    def test_regex_match_meter(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.*",
                        type="delta",
                        unit="B",
                        volume="$.payload.volume",
                        resource_id="$.payload.resource_id",
                        project_id="$.payload.project_id")]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(NOTIFICATION))
        self.assertEqual(1, len(c))

    def test_default_timestamp(self):
        event = copy.deepcopy(MIDDLEWARE_EVENT)
        del event['payload']['measurements'][1]
        cfg = yaml.dump(
            {'metric': [dict(name="$.payload.measurements.[*].metric.[*].name",
                        event_type="objectstore.http.request",
                        type="delta",
                        unit="$.payload.measurements.[*].metric.[*].unit",
                        volume="$.payload.measurements.[*].result",
                        resource_id="$.payload.target_id",
                        project_id="$.payload.initiator.project_id",
                        multi="name")]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(event))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        self.assertEqual(MIDDLEWARE_EVENT['timestamp'], s1['timestamp'])

    def test_custom_timestamp(self):
        event = copy.deepcopy(MIDDLEWARE_EVENT)
        del event['payload']['measurements'][1]
        cfg = yaml.dump(
            {'metric': [dict(name="$.payload.measurements.[*].metric.[*].name",
                        event_type="objectstore.http.request",
                        type="delta",
                        unit="$.payload.measurements.[*].metric.[*].unit",
                        volume="$.payload.measurements.[*].result",
                        resource_id="$.payload.target_id",
                        project_id="$.payload.initiator.project_id",
                        multi="name",
                        timestamp='$.payload.eventTime')]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(event))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        self.assertEqual(MIDDLEWARE_EVENT['payload']['eventTime'],
                         s1['timestamp'])

    def test_custom_timestamp_expr_meter(self):
        cfg = yaml.dump(
            {'metric': [dict(name='compute.node.cpu.frequency',
                        event_type="compute.metrics.update",
                        type='gauge',
                        unit="ns",
                        volume="$.payload.metrics[?(@.name='cpu.frequency')]"
                               ".value",
                        resource_id="'prefix-' + $.payload.nodename",
                        timestamp="$.payload.metrics"
                                  "[?(@.name='cpu.frequency')].timestamp")]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(METRICS_UPDATE))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        self.assertEqual('compute.node.cpu.frequency', s1['name'])
        self.assertEqual("2013-07-29T06:51:34.472416", s1['timestamp'])

    def test_default_metadata(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.*",
                        type="delta",
                        unit="B",
                        volume="$.payload.volume",
                        resource_id="$.payload.resource_id",
                        project_id="$.payload.project_id")]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(NOTIFICATION))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        meta = NOTIFICATION['payload'].copy()
        meta['host'] = NOTIFICATION['publisher_id']
        meta['event_type'] = NOTIFICATION['event_type']
        self.assertEqual(meta, s1['resource_metadata'])

    def test_datetime_plugin(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.*",
                        type="gauge",
                        unit="sec",
                        volume={"fields": ["$.payload.created_at",
                                           "$.payload.launched_at"],
                                "plugin": "timedelta"},
                        resource_id="$.payload.resource_id",
                        project_id="$.payload.project_id")]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(NOTIFICATION))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        self.assertEqual(5.0, s1['volume'])

    def test_custom_metadata(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.*",
                        type="delta",
                        unit="B",
                        volume="$.payload.volume",
                        resource_id="$.payload.resource_id",
                        project_id="$.payload.project_id",
                        metadata={'proj': '$.payload.project_id',
                                  'dict': '$.payload.resource_metadata'})]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(NOTIFICATION))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        meta = {'proj': s1['project_id'],
                'dict': NOTIFICATION['payload']['resource_metadata']}
        self.assertEqual(meta, s1['resource_metadata'])

    def test_multi_match_event_meter(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.create",
                        type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id"),
                        dict(name="test2",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id")]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(NOTIFICATION))
        self.assertEqual(2, len(c))

    def test_multi_meter_payload(self):
        cfg = yaml.dump(
            {'metric': [dict(name="$.payload.measurements.[*].metric.[*].name",
                        event_type="objectstore.http.request",
                        type="delta",
                        unit="$.payload.measurements.[*].metric.[*].unit",
                        volume="$.payload.measurements.[*].result",
                        resource_id="$.payload.target_id",
                        project_id="$.payload.initiator.project_id",
                        lookup=["name", "volume", "unit"])]})
        self._load_meter_def_file(cfg)
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
            {'metric': [dict(name="$.payload.measurements.[*].metric.[*].name",
                        event_type="objectstore.http.request",
                        type="delta",
                        unit="$.payload.measurements.[*].metric.[*].unit",
                        volume="$.payload.measurements.[*].result",
                        resource_id="$.payload.target_id",
                        project_id="$.payload.initiator.project_id",
                        lookup=["name", "unit"])]})
        self._load_meter_def_file(cfg)
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
            {'metric': [dict(name="$.payload.measurements.[*].metric.[*].name",
                        event_type="objectstore.http.request",
                        type="delta",
                        unit="$.payload.measurements.[*].metric.[*].unit",
                        volume="$.payload.measurements.[*].result",
                        resource_id="$.payload.target_id",
                        project_id="$.payload.initiator.project_id",
                        lookup="name")]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(event))
        self.assertEqual(0, len(c))

    def test_multi_meter_payload_all_multi(self):
        cfg = yaml.dump(
            {'metric': [dict(name="$.payload.[*].counter_name",
                        event_type="full.sample",
                        type="$.payload.[*].counter_type",
                        unit="$.payload.[*].counter_unit",
                        volume="$.payload.[*].counter_volume",
                        resource_id="$.payload.[*].resource_id",
                        project_id="$.payload.[*].project_id",
                        user_id="$.payload.[*].user_id",
                        lookup=['name', 'type', 'unit', 'volume',
                                'resource_id', 'project_id', 'user_id'])]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(FULL_MULTI_MSG))
        self.assertEqual(2, len(c))
        msg = FULL_MULTI_MSG['payload']
        for idx, val in enumerate(c):
            s1 = val.as_dict()
            self.assertEqual(msg[idx]['counter_name'], s1['name'])
            self.assertEqual(msg[idx]['counter_volume'], s1['volume'])
            self.assertEqual(msg[idx]['counter_unit'], s1['unit'])
            self.assertEqual(msg[idx]['counter_type'], s1['type'])
            self.assertEqual(msg[idx]['resource_id'], s1['resource_id'])
            self.assertEqual(msg[idx]['project_id'], s1['project_id'])
            self.assertEqual(msg[idx]['user_id'], s1['user_id'])

    @mock.patch('ceilometer.meter.notifications.LOG')
    def test_multi_meter_payload_invalid_missing(self, LOG):
        event = copy.deepcopy(MIDDLEWARE_EVENT)
        del event['payload']['measurements'][0]['result']
        del event['payload']['measurements'][1]['result']
        cfg = yaml.dump(
            {'metric': [dict(name="$.payload.measurements.[*].metric.[*].name",
                        event_type="objectstore.http.request",
                        type="delta",
                        unit="$.payload.measurements.[*].metric.[*].unit",
                        volume="$.payload.measurements.[*].result",
                        resource_id="$.payload.target_id",
                        project_id="$.payload.initiator.project_id",
                        lookup=["name", "unit", "volume"])]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(event))
        self.assertEqual(0, len(c))
        LOG.warning.assert_called_with('Only 0 fetched meters contain '
                                       '"volume" field instead of 2.')

    @mock.patch('ceilometer.meter.notifications.LOG')
    def test_multi_meter_payload_invalid_short(self, LOG):
        event = copy.deepcopy(MIDDLEWARE_EVENT)
        del event['payload']['measurements'][0]['result']
        cfg = yaml.dump(
            {'metric': [dict(name="$.payload.measurements.[*].metric.[*].name",
                        event_type="objectstore.http.request",
                        type="delta",
                        unit="$.payload.measurements.[*].metric.[*].unit",
                        volume="$.payload.measurements.[*].result",
                        resource_id="$.payload.target_id",
                        project_id="$.payload.initiator.project_id",
                        lookup=["name", "unit", "volume"])]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(event))
        self.assertEqual(0, len(c))
        LOG.warning.assert_called_with('Only 1 fetched meters contain '
                                       '"volume" field instead of 2.')

    def test_arithmetic_expr_meter(self):
        cfg = yaml.dump(
            {'metric': [dict(name='compute.node.cpu.percent',
                        event_type="compute.metrics.update",
                        type='gauge',
                        unit="percent",
                        volume="$.payload.metrics["
                               "?(@.name='cpu.percent')].value"
                               " * 100",
                        resource_id="$.payload.host + '_'"
                                    " + $.payload.nodename")]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(METRICS_UPDATE))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        self.assertEqual('compute.node.cpu.percent', s1['name'])
        self.assertEqual(2.7501485834103514, s1['volume'])
        self.assertEqual("tianst_tianst.sh.intel.com",
                         s1['resource_id'])

    def test_string_expr_meter(self):
        cfg = yaml.dump(
            {'metric': [dict(name='compute.node.cpu.frequency',
                        event_type="compute.metrics.update",
                        type='gauge',
                        unit="ns",
                        volume="$.payload.metrics[?(@.name='cpu.frequency')]"
                               ".value",
                        resource_id="$.payload.host + '_'"
                                    " + $.payload.nodename")]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(METRICS_UPDATE))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        self.assertEqual('compute.node.cpu.frequency', s1['name'])
        self.assertEqual(1600, s1['volume'])
        self.assertEqual("tianst_tianst.sh.intel.com",
                         s1['resource_id'])

    def test_prefix_expr_meter(self):
        cfg = yaml.dump(
            {'metric': [dict(name='compute.node.cpu.frequency',
                        event_type="compute.metrics.update",
                        type='gauge',
                        unit="ns",
                        volume="$.payload.metrics[?(@.name='cpu.frequency')]"
                               ".value",
                        resource_id="'prefix-' + $.payload.nodename")]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(METRICS_UPDATE))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        self.assertEqual('compute.node.cpu.frequency', s1['name'])
        self.assertEqual(1600, s1['volume'])
        self.assertEqual("prefix-tianst.sh.intel.com",
                         s1['resource_id'])

    def test_duplicate_meter(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id"),
                        dict(name="test1",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id")]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.process_notification(NOTIFICATION))
        self.assertEqual(1, len(c))
