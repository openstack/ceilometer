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
"""Tests for ceilometer.meter.notifications"""
import copy
from unittest import mock

import fixtures
from oslo_utils import encodeutils
from oslo_utils import fileutils
import yaml

from ceilometer import declarative
from ceilometer.meter import notifications
from ceilometer import service as ceilometer_service
from ceilometer.tests import base as test

NOTIFICATION = {
    'event_type': 'test.create',
    'metadata': {'timestamp': '2015-06-19T09:19:35.786893',
                 'message_id': '939823de-c242-45a2-a399-083f4d6a8c3e'},
    'payload': {'user_id': 'e1d870e51c7340cb9d555b15cbfcaec2',
                'resource_id': 'bea70e51c7340cb9d555b15cbfcaec23',
                'timestamp': '2015-06-19T09:19:35.785330',
                'created_at': '2015-06-19T09:25:35.785330',
                'launched_at': '2015-06-19T09:25:40.785330',
                'message_signature': 'fake_signature1',
                'resource_metadata': {'foo': 'bar'},
                'source': '30be1fc9a03c4e94ab05c403a8a377f2: openstack',
                'volume': 1.0,
                'project_id': '30be1fc9a03c4e94ab05c403a8a377f2',
                },
    'ctxt': {'tenant': '30be1fc9a03c4e94ab05c403a8a377f2',
             'request_id': 'req-da91b4bf-d2b5-43ae-8b66-c7752e72726d',
             'user': 'e1d870e51c7340cb9d555b15cbfcaec2'},
    'publisher_id': "foo123"
}

USER_META = {
    'event_type': 'test.create',
    'metadata': {'timestamp': '2015-06-19T09:19:35.786893',
                 'message_id': '939823de-c242-45a2-a399-083f4d6a8c3e'},
    'payload': {'user_id': 'e1d870e51c7340cb9d555b15cbfcaec2',
                'resource_id': 'bea70e51c7340cb9d555b15cbfcaec23',
                'timestamp': '2015-06-19T09:19:35.785330',
                'created_at': '2015-06-19T09:25:35.785330',
                'launched_at': '2015-06-19T09:25:40.785330',
                'message_signature': 'fake_signature1',
                'resource_metadata': {'foo': 'bar'},
                'source': '30be1fc9a03c4e94ab05c403a8a377f2: openstack',
                'volume': 1.0,
                'project_id': '30be1fc9a03c4e94ab05c403a8a377f2',
                'metadata': {'metering.xyz': 'abc', 'ignore': 'this'},
                },
    'ctxt': {'tenant': '30be1fc9a03c4e94ab05c403a8a377f2',
             'request_id': 'req-da91b4bf-d2b5-43ae-8b66-c7752e72726d',
             'user': 'e1d870e51c7340cb9d555b15cbfcaec2'},
    'publisher_id': "foo123"
}

MIDDLEWARE_EVENT = {
    'ctxt': {'request_id': 'req-a8bfa89b-d28b-4b95-9e4b-7d7875275650',
             'quota_class': None,
             'service_catalog': [],
             'auth_token': None,
             'user_id': None,
             'is_admin': True,
             'user': None,
             'remote_address': None,
             'roles': [],
             'timestamp': '2013-07-29T06:51:34.348091',
             'project_name': None,
             'read_deleted': 'no',
             'tenant': None,
             'instance_lock_checked': False,
             'project_id': None,
             'user_name': None},
    'event_type': 'objectstore.http.request',
    'publisher_id': 'ceilometermiddleware',
    'metadata': {'message_id': '6eccedba-120e-4db8-9735-2ad5f061e5ee',
                  'timestamp': '2013-07-29T06:51:34.474815+00:00',
                  '_unique_id': '0ee26117077648e18d88ac76e28a72e2'},
    'payload': {
        'typeURI': 'http: //schemas.dmtf.org/cloud/audit/1.0/event',
        'eventTime': '2013-07-29T06:51:34.474815+00:00',
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
    'event_type': 'full.sample',
    'payload': [{
                'counter_name': 'instance1',
                'user_id': 'user1',
                'user_name': 'test-resource',
                'resource_id': 'res1',
                'counter_unit': 'ns',
                'counter_volume': 28.0,
                'project_id': 'proj1',
                'project_name': 'test-resource',
                'counter_type': 'gauge'
                },
                {
                'counter_name': 'instance2',
                'user_id': 'user2',
                'user_name': 'test-resource',
                'resource_id': 'res2',
                'counter_unit': '%',
                'counter_volume': 1.0,
                'project_id': 'proj2',
                'project_name': 'test-resource',
                'counter_type': 'delta'
                }],
    'ctxt': {'domain': None,
             'request_id': 'req-da91b4bf-d2b5-43ae-8b66-c7752e72726d',
             'auth_token': None,
             'read_only': False,
             'resource_uuid': None,
             'user_identity': 'fake_user_identity---',
             'show_deleted': False,
             'tenant': '30be1fc9a03c4e94ab05c403a8a377f2',
             'is_admin': True,
             'project_domain': None,
             'user': 'e1d870e51c7340cb9d555b15cbfcaec2',
             'user_domain': None},
    'publisher_id': 'ceilometer.api',
    'metadata': {'message_id': '939823de-c242-45a2-a399-083f4d6a8c3e',
                 'timestamp': '2015-06-19T09:19:35.786893'},
}

METRICS_UPDATE = {
    'event_type': 'compute.metrics.update',
    'payload': {
        'metrics': [
            {'timestamp': '2013-07-29T06:51:34.472416',
             'name': 'cpu.frequency', 'value': 1600,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': '2013-07-29T06:51:34.472416',
             'name': 'cpu.user.time', 'value': 17421440000000,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': '2013-07-29T06:51:34.472416',
             'name': 'cpu.kernel.time', 'value': 7852600000000,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': '2013-07-29T06:51:34.472416',
             'name': 'cpu.idle.time', 'value': 1307374400000000,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': '2013-07-29T06:51:34.472416',
             'name': 'cpu.iowait.time', 'value': 11697470000000,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': '2013-07-29T06:51:34.472416',
             'name': 'cpu.user.percent', 'value': 0.012959045637294348,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': '2013-07-29T06:51:34.472416',
             'name': 'cpu.kernel.percent', 'value': 0.005841204961898534,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': '2013-07-29T06:51:34.472416',
             'name': 'cpu.idle.percent', 'value': 0.9724985141658965,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': '2013-07-29T06:51:34.472416',
             'name': 'cpu.iowait.percent', 'value': 0.008701235234910634,
             'source': 'libvirt.LibvirtDriver'},
            {'timestamp': '2013-07-29T06:51:34.472416',
             'name': 'cpu.percent', 'value': 0.027501485834103515,
             'source': 'libvirt.LibvirtDriver'}],
        'nodename': 'tianst.sh.intel.com',
        'host': 'tianst',
        'host_id': '10.0.1.1'},
    'publisher_id': 'compute.tianst.sh.intel.com',
    'metadata': {'message_id': '6eccedba-120e-4db8-9735-2ad5f061e5ee',
                 'timestamp': '2013-07-29 06:51:34.474815',
                 '_unique_id': '0ee26117077648e18d88ac76e28a72e2'},
    'ctxt': {'request_id': 'req-a8bfa89b-d28b-4b95-9e4b-7d7875275650',
             'quota_class': None,
             'service_catalog': [],
             'auth_token': None,
             'user_id': None,
             'is_admin': True,
             'user': None,
             'remote_address': None,
             'roles': [],
             'timestamp': '2013-07-29T06:51:34.348091',
             'project_name': None,
             'read_deleted': 'no',
             'tenant': None,
             'instance_lock_checked': False,
             'project_id': None,
             'user_name': None}
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
        handler = notifications.MeterDefinition(cfg, mock.Mock(), mock.Mock())
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
            notifications.MeterDefinition(cfg, mock.Mock(), mock.Mock())
        except declarative.DefinitionException as e:
            self.assertIn("Required fields ['name', 'type', 'event_type',"
                          " 'unit', 'volume', 'resource_id']"
                          " not specified",
                          encodeutils.exception_to_unicode(e))

    def test_bad_type_cfg_definition(self):
        cfg = dict(name="test", type="foo", event_type="bar.create",
                   unit="foo", volume="bar",
                   resource_id="bea70e51c7340cb9d555b15cbfcaec23")
        try:
            notifications.MeterDefinition(cfg, mock.Mock(), mock.Mock())
        except declarative.DefinitionException as e:
            self.assertIn("Invalid type foo specified",
                          encodeutils.exception_to_unicode(e))


class TestMeterProcessing(test.BaseTestCase):

    def setUp(self):
        super(TestMeterProcessing, self).setUp()
        self.CONF = ceilometer_service.prepare_service([], [])
        self.path = self.useFixture(fixtures.TempDir()).path
        self.handler = notifications.ProcessMeterNotifications(
            self.CONF, mock.Mock())

    def _load_meter_def_file(self, cfgs=None):
        self.CONF.set_override('meter_definitions_dirs',
                               [self.path], group='meter')
        cfgs = cfgs or []
        if not isinstance(cfgs, list):
            cfgs = [cfgs]
        meter_cfg_files = list()
        for cfg in cfgs:
            cfg = cfg.encode('utf-8')
            meter_cfg_files.append(fileutils.write_to_tempfile(content=cfg,
                                                               path=self.path,
                                                               prefix="meters",
                                                               suffix=".yaml"))
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
        args, kwargs = LOG.error.call_args_list[0]
        self.assertEqual("Error loading meter definition: %s", args[0])
        self.assertTrue(args[1].endswith("Invalid type bad_type specified"))

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
        c = list(self.handler.build_sample(NOTIFICATION))
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
        data = list(self.handler.build_sample(NOTIFICATION))
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
        c = list(self.handler.build_sample(NOTIFICATION))
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
        c = list(self.handler.build_sample(NOTIFICATION))
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
        c = list(self.handler.build_sample(event))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        self.assertEqual(MIDDLEWARE_EVENT['metadata']['timestamp'],
                         s1['timestamp'])

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
        c = list(self.handler.build_sample(event))
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
        c = list(self.handler.build_sample(METRICS_UPDATE))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        self.assertEqual('compute.node.cpu.frequency', s1['name'])
        self.assertEqual("2013-07-29T06:51:34.472416+00:00", s1['timestamp'])

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
        c = list(self.handler.build_sample(NOTIFICATION))
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
        c = list(self.handler.build_sample(NOTIFICATION))
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
        c = list(self.handler.build_sample(NOTIFICATION))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        meta = {'proj': s1['project_id'],
                'dict': NOTIFICATION['payload']['resource_metadata']}
        self.assertEqual(meta, s1['resource_metadata'])

    def test_user_meta(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.*",
                        type="delta",
                        unit="B",
                        volume="$.payload.volume",
                        resource_id="$.payload.resource_id",
                        project_id="$.payload.project_id",
                        user_metadata="$.payload.metadata",)]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.build_sample(USER_META))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        meta = {'user_metadata': {'xyz': 'abc'}}
        self.assertEqual(meta, s1['resource_metadata'])

    def test_user_meta_and_custom(self):
        cfg = yaml.dump(
            {'metric': [dict(name="test1",
                        event_type="test.*",
                        type="delta",
                        unit="B",
                        volume="$.payload.volume",
                        resource_id="$.payload.resource_id",
                        project_id="$.payload.project_id",
                        user_metadata="$.payload.metadata",
                        metadata={'proj': '$.payload.project_id'})]})
        self._load_meter_def_file(cfg)
        c = list(self.handler.build_sample(USER_META))
        self.assertEqual(1, len(c))
        s1 = c[0].as_dict()
        meta = {'user_metadata': {'xyz': 'abc'}, 'proj': s1['project_id']}
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
        c = list(self.handler.build_sample(NOTIFICATION))
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
        c = list(self.handler.build_sample(MIDDLEWARE_EVENT))
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
        c = list(self.handler.build_sample(event))
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
        c = list(self.handler.build_sample(event))
        self.assertEqual(0, len(c))

    @mock.patch('ceilometer.cache_utils.resolve_uuid_from_cache')
    def test_multi_meter_payload_all_multi(self, fake_cached_resource_name):

        # return "test-resource" as the name of the user and project from cache
        fake_cached_resource_name.return_value = "test-resource"

        # expect user_name and project_name values to be set to "test-resource"
        fake_user_name = "test-resource"
        fake_project_name = "test-resource"

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
        c = list(self.handler.build_sample(FULL_MULTI_MSG))
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
            self.assertEqual(fake_user_name, s1['user_name'])
            self.assertEqual(fake_project_name, s1['project_name'])

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
        c = list(self.handler.build_sample(event))
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
        c = list(self.handler.build_sample(event))
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
        c = list(self.handler.build_sample(METRICS_UPDATE))
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
        c = list(self.handler.build_sample(METRICS_UPDATE))
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
        c = list(self.handler.build_sample(METRICS_UPDATE))
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
        c = list(self.handler.build_sample(NOTIFICATION))
        self.assertEqual(1, len(c))

    def test_multi_files_multi_meters(self):
        cfg1 = yaml.dump(
            {'metric': [dict(name="test1",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id")]})
        cfg2 = yaml.dump(
            {'metric': [dict(name="test2",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id")]})
        self._load_meter_def_file([cfg1, cfg2])
        data = list(self.handler.build_sample(NOTIFICATION))
        self.assertEqual(2, len(data))
        expected_names = ['test1', 'test2']
        for s in data:
            self.assertIn(s.as_dict()['name'], expected_names)

    def test_multi_files_duplicate_meter(self):
        cfg1 = yaml.dump(
            {'metric': [dict(name="test",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id")]})
        cfg2 = yaml.dump(
            {'metric': [dict(name="test",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id")]})
        self._load_meter_def_file([cfg1, cfg2])
        data = list(self.handler.build_sample(NOTIFICATION))
        self.assertEqual(1, len(data))
        self.assertEqual(data[0].as_dict()['name'], 'test')

    def test_multi_files_empty_payload(self):
        event = copy.deepcopy(MIDDLEWARE_EVENT)
        del event['payload']['measurements']
        cfg1 = yaml.dump(
            {'metric': [dict(name="$.payload.measurements.[*].metric.[*].name",
                             event_type="objectstore.http.request",
                             type="delta",
                             unit="$.payload.measurements.[*].metric.[*].unit",
                             volume="$.payload.measurements.[*].result",
                             resource_id="$.payload.target_id",
                             project_id="$.payload.initiator.project_id",
                             lookup="name")]})
        cfg2 = yaml.dump(
            {'metric': [dict(name="$.payload.measurements.[*].metric.[*].name",
                             event_type="objectstore.http.request",
                             type="delta",
                             unit="$.payload.measurements.[*].metric.[*].unit",
                             volume="$.payload.measurements.[*].result",
                             resource_id="$.payload.target_id",
                             project_id="$.payload.initiator.project_id",
                             lookup="name")]})
        self._load_meter_def_file([cfg1, cfg2])
        data = list(self.handler.build_sample(event))
        self.assertEqual(0, len(data))

    def test_multi_files_unmatched_meter(self):
        cfg1 = yaml.dump(
            {'metric': [dict(name="test1",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id")]})
        cfg2 = yaml.dump(
            {'metric': [dict(name="test2",
                        event_type="test.update",
                        type="delta",
                        unit="B",
                        volume="$.payload.volume",
                        resource_id="$.payload.resource_id",
                        project_id="$.payload.project_id")]})
        self._load_meter_def_file([cfg1, cfg2])
        data = list(self.handler.build_sample(NOTIFICATION))
        self.assertEqual(1, len(data))
        self.assertEqual(data[0].as_dict()['name'], 'test1')

    @mock.patch('ceilometer.meter.notifications.LOG')
    def test_multi_files_bad_meter(self, LOG):
        cfg1 = yaml.dump(
            {'metric': [dict(name="test1",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id"),
                        dict(name="bad_test",
                             type="bad_type",
                             event_type="bar.create",
                             unit="foo", volume="bar",
                             resource_id="bea70e51c7340cb9d555b15cbfcaec23")]})
        cfg2 = yaml.dump(
            {'metric': [dict(name="test2",
                             event_type="test.create",
                             type="delta",
                             unit="B",
                             volume="$.payload.volume",
                             resource_id="$.payload.resource_id",
                             project_id="$.payload.project_id")]})
        self._load_meter_def_file([cfg1, cfg2])
        data = list(self.handler.build_sample(NOTIFICATION))
        self.assertEqual(2, len(data))
        expected_names = ['test1', 'test2']
        for s in data:
            self.assertIn(s.as_dict()['name'], expected_names)
        args, kwargs = LOG.error.call_args_list[0]
        self.assertEqual("Error loading meter definition: %s", args[0])
        self.assertTrue(args[1].endswith("Invalid type bad_type specified"))
