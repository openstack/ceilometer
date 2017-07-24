#
# Copyright 2014 eNovance
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

import os
import uuid

import fixtures
from gnocchiclient import exceptions as gnocchi_exc
from keystoneauth1 import exceptions as ka_exceptions
import mock
from oslo_config import fixture as config_fixture
from oslo_utils import fileutils
from oslo_utils import fixture as utils_fixture
from oslo_utils import timeutils
import requests
import six
from stevedore import extension
import testscenarios

from ceilometer.dispatcher import gnocchi
from ceilometer.publisher import utils
from ceilometer import service as ceilometer_service
from ceilometer.tests import base

load_tests = testscenarios.load_tests_apply_scenarios

INSTANCE_DELETE_START = {
    'event_type': u'compute.instance.delete.start',
    'traits': [
        [
            'state',
            1,
            u'active'
        ],
        [
            'user_id',
            1,
            u'1e3ce043029547f1a61c1996d1a531a2'
        ],
        [
            'service',
            1,
            u'compute'
        ],
        [
            'disk_gb',
            2,
            0
        ],
        [
            'instance_type',
            1,
            u'm1.tiny'
        ],
        [
            'tenant_id',
            1,
            u'7c150a59fe714e6f9263774af9688f0e'
        ],
        [
            'root_gb',
            2,
            0
        ],
        [
            'ephemeral_gb',
            2,
            0
        ],
        [
            'instance_type_id',
            2,
            2
        ],
        [
            'vcpus',
            2,
            1
        ],
        [
            'memory_mb',
            2,
            512
        ],
        [
            'instance_id',
            1,
            u'9f9d01b9-4a58-4271-9e27-398b21ab20d1'
        ],
        [
            'host',
            1,
            u'vagrant-precise'
        ],
        [
            'request_id',
            1,
            u'req-fb3c4546-a2e5-49b7-9fd2-a63bd658bc39'
        ],
        [
            'project_id',
            1,
            u'7c150a59fe714e6f9263774af9688f0e'
        ],
        [
            'launched_at',
            4,
            '2012-05-08T20:23:47'
        ]
    ],
    'message_signature':
        '831719d54059734f82e7d6498c6d7a8fd637568732e79c1fd375e128f142373a',
    'raw': {},
    'generated': '2012-05-08T20:24:14.824743',
    'message_id': u'a15b94ee-cb8e-4c71-9abe-14aa80055fb4'
}

IMAGE_DELETE_START = {
    u'event_type': u'image.delete',
    u'traits': [
        [
            u'status',
            1,
            u'deleted'
        ],
        [
            u'deleted_at',
            1,
            u'2016-11-04T04:25:56Z'
        ],
        [
            u'user_id',
            1,
            u'e97ef33a20ed4843b520d223f3cc33d4'
        ],
        [
            u'name',
            1,
            u'cirros'
        ],
        [
            u'service',
            1,
            u'image.localhost'
        ],
        [
            u'resource_id',
            1,
            u'dc337359-de70-4044-8e2c-80573ba6e577'
        ],
        [
            u'created_at',
            1,
            u'2016-11-04T04:24:36Z'
        ],
        [
            u'project_id',
            1,
            u'e97ef33a20ed4843b520d223f3cc33d4'
        ],
        [
            u'size',
            1,
            u'13287936'
        ]
    ],
    u'message_signature':
        u'46fb4958e911f45007a3bb5934c5de7610892a6d742a4900695fd5929cd4c9b3',
    u'raw': {},
    u'generated': u'2016-11-04T04:25:56.493820',
    u'message_id': u'7f5280f7-1d10-46a5-ba58-4d5508e49f99'
}


VOLUME_DELETE_START = {
    'event_type': u'volume.delete.start',
    'traits': [
        [
            u'availability_zone',
            1,
            u'nova'
        ],
        [
            u'created_at',
            1,
            u'2016-11-28T13:19:53+00:00'
        ],
        [
            u'display_name',
            1,
            u'vol-001'
        ],
        [
            u'host',
            1,
            u'zhangguoqing-dev@lvmdriver-1#lvmdriver-1'
        ],
        [
            u'project_id',
            1,
            u'd53fcc7dc53c4662ad77822c36a21f00'
        ],
        [
            u'replication_status',
            1,
            u'disabled'
        ],
        [
            u'request_id',
            1,
            u'req-f44df096-50d4-4211-95ea-64be6f5e4f60'
        ],
        [
            u'resource_id',
            1,
            u'6cc6e7dd-d17d-460f-ae79-7e08a216ce96'
        ],
        [
            u'service',
            1,
            u'volume.zhangguoqing-dev@lvmdriver-1'
        ],
        [
            u'size',
            1,
            u'1'
        ],
        [
            u'status',
            1,
            u'deleting'
        ],
        [
            u'tenant_id',
            1,
            u'd53fcc7dc53c4662ad77822c36a21f00'
        ],
        [
            u'type',
            1,
            u'af6271fa-13c4-44e6-9246-754ce9dc7df8'
        ],
        [
            u'user_id',
            1,
            u'819bbd28f5374506b8502521c89430b5'
        ]
    ],
    'message_signature':
        '831719d54059734f82e7d6498c6d7a8fd637568732e79c1fd375e128f142373a',
    'raw': {},
    'generated': '2016-11-28T13:42:15.484674',
    'message_id': u'a15b94ee-cb8e-4c71-9abe-14aa80055fb4'
}

FLOATINGIP_DELETE_END = {
    'event_type': u'floatingip.delete.end',
    'traits': [
        [
            u'project_id',
            1,
            u'd53fcc7dc53c4662ad77822c36a21f00'
        ],
        [
            u'request_id',
            1,
            'req-443ddb77-31f7-41fe-abbf-921107dd9f00'
        ],
        [
            u'resource_id',
            1,
            u'705e2c08-08e8-45cb-8673-5c5be955569b'
        ],
        [
            u'service',
            1,
            u'network.zhangguoqing-dev'
        ],
        [
            u'tenant_id',
            1,
            u'd53fcc7dc53c4662ad77822c36a21f00'
        ],
        [
            u'user_id',
            1,
            u'819bbd28f5374506b8502521c89430b5'
        ]
    ],
    'message_signature':
        '831719d54059734f82e7d6498c6d7a8fd637568732e79c1fd375e128f142373a',
    'raw': {},
    'generated': '2016-11-29T09:25:55.474710',
    'message_id': u'a15b94ee-cb8e-4c71-9abe-14aa80055fb4'
}


class DispatcherTest(base.BaseTestCase):

    def setUp(self):
        super(DispatcherTest, self).setUp()
        conf = ceilometer_service.prepare_service(argv=[], config_files=[])
        self.conf = self.useFixture(config_fixture.Config(conf))
        self.conf.config(
            resources_definition_file=self.path_get(
                'etc/ceilometer/gnocchi_resources.yaml'),
            group="dispatcher_gnocchi"
        )
        self.resource_id = str(uuid.uuid4())
        self.samples = [{
            'counter_name': 'disk.root.size',
            'counter_unit': 'GB',
            'counter_type': 'gauge',
            'counter_volume': '2',
            'user_id': 'test_user',
            'project_id': 'test_project',
            'source': 'openstack',
            'timestamp': '2012-05-08 20:23:48.028195',
            'resource_id': self.resource_id,
            'resource_metadata': {
                'host': 'foo',
                'image_ref': 'imageref!',
                'instance_flavor_id': 1234,
                'display_name': 'myinstance',
                }
            },
            {
                'counter_name': 'disk.root.size',
                'counter_unit': 'GB',
                'counter_type': 'gauge',
                'counter_volume': '2',
                'user_id': 'test_user',
                'project_id': 'test_project',
                'source': 'openstack',
                'timestamp': '2014-05-08 20:23:48.028195',
                'resource_id': self.resource_id,
                'resource_metadata': {
                    'host': 'foo',
                    'image_ref': 'imageref!',
                    'instance_flavor_id': 1234,
                    'display_name': 'myinstance',
                }
            }]
        for sample in self.samples:
            sample['message_signature'] = utils.compute_signature(
                sample, self.conf.conf.publisher.telemetry_secret)

        ks_client = mock.Mock(auth_token='fake_token')
        ks_client.projects.find.return_value = mock.Mock(
            name='gnocchi', id='a2d42c23-d518-46b6-96ab-3fba2e146859')
        self.useFixture(fixtures.MockPatch(
            'ceilometer.keystone_client.get_client',
            return_value=ks_client))
        self.ks_client = ks_client
        self.conf.conf.dispatcher_gnocchi.filter_service_activity = True

    def test_config_load(self):
        self.conf.config(filter_service_activity=False,
                         group='dispatcher_gnocchi')
        d = gnocchi.GnocchiDispatcher(self.conf.conf)
        names = [rd.cfg['resource_type'] for rd in d.resources_definition]
        self.assertIn('instance', names)
        self.assertIn('volume', names)

    def test_match(self):
        resource = {
            'metrics':
                ['image', 'image.size', 'image.download', 'image.serve'],
            'attributes':
                {'container_format': 'resource_metadata.container_format',
                 'disk_format': 'resource_metadata.disk_format',
                 'name': 'resource_metadata.name'},
            'event_delete': 'image.delete',
            'event_attributes': {'id': 'resource_id'},
            'resource_type': 'image'}
        plugin_manager = extension.ExtensionManager(
            namespace='ceilometer.event.trait.trait_plugin')
        rd = gnocchi.ResourcesDefinition(
            resource, self.conf.conf.dispatcher_gnocchi.archive_policy,
            plugin_manager)
        operation = rd.event_match("image.delete")
        self.assertEqual('delete', operation)
        self.assertEqual(True, rd.metric_match('image'))

    @mock.patch('ceilometer.dispatcher.gnocchi.LOG')
    def test_broken_config_load(self, mylog):
        contents = [("---\n"
                     "resources:\n"
                     "  - resource_type: foobar\n"),
                    ("---\n"
                     "resources:\n"
                     "  - resource_type: 0\n"),
                    ("---\n"
                     "resources:\n"
                     "  - sample_types: ['foo', 'bar']\n"),
                    ("---\n"
                     "resources:\n"
                     "  - sample_types: foobar\n"
                     "  - resource_type: foobar\n"),
                    ]

        for content in contents:
            if six.PY3:
                content = content.encode('utf-8')

            temp = fileutils.write_to_tempfile(content=content,
                                               prefix='gnocchi_resources',
                                               suffix='.yaml')
            self.addCleanup(os.remove, temp)
            self.conf.config(filter_service_activity=False,
                             resources_definition_file=temp,
                             group='dispatcher_gnocchi')
            d = gnocchi.GnocchiDispatcher(self.conf.conf)
            self.assertTrue(mylog.error.called)
            self.assertEqual(0, len(d.resources_definition))

    @mock.patch('ceilometer.dispatcher.gnocchi.GnocchiDispatcher'
                '._if_not_cached')
    @mock.patch('ceilometer.dispatcher.gnocchi.GnocchiDispatcher'
                '.batch_measures')
    def _do_test_activity_filter(self, expected_measures, fake_batch, __):

        d = gnocchi.GnocchiDispatcher(self.conf.conf)
        d.record_metering_data(self.samples)
        fake_batch.assert_called_with(
            mock.ANY, mock.ANY,
            {'metrics': 1, 'resources': 1, 'measures': expected_measures})

    def test_activity_filter_match_project_id(self):
        self.samples[0]['project_id'] = (
            'a2d42c23-d518-46b6-96ab-3fba2e146859')
        self._do_test_activity_filter(1)

    @mock.patch('ceilometer.dispatcher.gnocchi.LOG')
    def test_activity_gnocchi_project_not_found(self, logger):
        self.ks_client.projects.find.side_effect = ka_exceptions.NotFound
        self._do_test_activity_filter(2)
        logger.warning.assert_called_with('gnocchi project not found in '
                                          'keystone, ignoring the '
                                          'filter_service_activity option')

    def test_activity_filter_match_swift_event(self):
        self.samples[0]['counter_name'] = 'storage.api.request'
        self.samples[0]['resource_id'] = 'a2d42c23-d518-46b6-96ab-3fba2e146859'
        self._do_test_activity_filter(1)

    def test_activity_filter_nomatch(self):
        self._do_test_activity_filter(2)

    @mock.patch('ceilometer.dispatcher.gnocchi.GnocchiDispatcher'
                '.batch_measures')
    def test_unhandled_meter(self, fake_batch):
        samples = [{
            'counter_name': 'unknown.meter',
            'counter_unit': 'GB',
            'counter_type': 'gauge',
            'counter_volume': '2',
            'user_id': 'test_user',
            'project_id': 'test_project',
            'source': 'openstack',
            'timestamp': '2014-05-08 20:23:48.028195',
            'resource_id': 'randomid',
            'resource_metadata': {}
        }]
        d = gnocchi.GnocchiDispatcher(self.conf.conf)
        d.record_metering_data(samples)
        self.assertEqual(0, len(fake_batch.call_args[0][1]))


class MockResponse(mock.NonCallableMock):
    def __init__(self, code):
        text = {500: 'Internal Server Error',
                404: 'Not Found',
                204: 'Created',
                409: 'Conflict',
                }.get(code)
        super(MockResponse, self).__init__(spec=requests.Response,
                                           status_code=code,
                                           text=text)


class DispatcherWorkflowTest(base.BaseTestCase,
                             testscenarios.TestWithScenarios):

    sample_scenarios = [
        ('disk.root.size', dict(
            sample={
                'counter_name': 'disk.root.size',
                'counter_unit': 'GB',
                'counter_type': 'gauge',
                'counter_volume': '2',
                'user_id': 'test_user',
                'project_id': 'test_project',
                'source': 'openstack',
                'timestamp': '2012-05-08 20:23:48.028195',
                'resource_metadata': {
                    'host': 'foo',
                    'image_ref': 'imageref!',
                    'instance_flavor_id': 1234,
                    'display_name': 'myinstance',
                }
            },
            measures_attributes=[{
                'timestamp': '2012-05-08 20:23:48.028195',
                'value': '2'
            }],
            postable_attributes={
                'user_id': 'test_user',
                'project_id': 'test_project',
            },
            patchable_attributes={
                'host': 'foo',
                'image_ref': 'imageref!',
                'flavor_id': 1234,
                'display_name': 'myinstance',
            },
            metric_names=[
                'disk.root.size', 'disk.ephemeral.size',
                'memory', 'vcpus', 'memory.usage', 'memory.resident',
                'memory.swap.in', 'memory.swap.out',
                'memory.bandwidth.total', 'memory.bandwidth.local',
                'cpu', 'cpu.delta', 'cpu_util', 'vcpus', 'disk.read.requests',
                'cpu_l3_cache', 'perf.cpu.cycles', 'perf.instructions',
                'perf.cache.references', 'perf.cache.misses',
                'disk.read.requests.rate', 'disk.write.requests',
                'disk.write.requests.rate', 'disk.read.bytes',
                'disk.read.bytes.rate', 'disk.write.bytes',
                'disk.write.bytes.rate', 'disk.latency', 'disk.iops',
                'disk.capacity', 'disk.allocation', 'disk.usage',
                'compute.instance.booting.time'],
            resource_type='instance')),
        ('hardware.ipmi.node.power', dict(
            sample={
                'counter_name': 'hardware.ipmi.node.power',
                'counter_unit': 'W',
                'counter_type': 'gauge',
                'counter_volume': '2',
                'user_id': 'test_user',
                'project_id': 'test_project',
                'source': 'openstack',
                'timestamp': '2012-05-08 20:23:48.028195',
                'resource_metadata': {
                    'useless': 'not_used',
                }
            },
            measures_attributes=[{
                'timestamp': '2012-05-08 20:23:48.028195',
                'value': '2'
            }],
            postable_attributes={
                'user_id': 'test_user',
                'project_id': 'test_project',
            },
            patchable_attributes={
            },
            metric_names=[
                'hardware.ipmi.node.power', 'hardware.ipmi.node.temperature',
                'hardware.ipmi.node.inlet_temperature',
                'hardware.ipmi.node.outlet_temperature',
                'hardware.ipmi.node.fan', 'hardware.ipmi.node.current',
                'hardware.ipmi.node.voltage', 'hardware.ipmi.node.airflow',
                'hardware.ipmi.node.cups', 'hardware.ipmi.node.cpu_util',
                'hardware.ipmi.node.mem_util', 'hardware.ipmi.node.io_util'
            ],
            resource_type='ipmi')),
    ]

    default_workflow = dict(resource_exists=True,
                            post_measure_fail=False,
                            create_resource_fail=False,
                            create_resource_race=False,
                            update_resource_fail=False,
                            retry_post_measures_fail=False)
    workflow_scenarios = [
        ('normal_workflow', {}),
        ('new_resource', dict(resource_exists=False)),
        ('new_resource_compat', dict(resource_exists=False)),
        ('new_resource_fail', dict(resource_exists=False,
                                   create_resource_fail=True)),
        ('new_resource_race', dict(resource_exists=False,
                                   create_resource_race=True)),
        ('resource_update_fail', dict(update_resource_fail=True)),
        ('retry_fail', dict(resource_exists=False,
                            retry_post_measures_fail=True)),
        ('measure_fail', dict(post_measure_fail=True)),
    ]

    @classmethod
    def generate_scenarios(cls):
        workflow_scenarios = []
        for name, wf_change in cls.workflow_scenarios:
            wf = cls.default_workflow.copy()
            wf.update(wf_change)
            workflow_scenarios.append((name, wf))
        cls.scenarios = testscenarios.multiply_scenarios(cls.sample_scenarios,
                                                         workflow_scenarios)

    def setUp(self):
        super(DispatcherWorkflowTest, self).setUp()
        conf = ceilometer_service.prepare_service(argv=[], config_files=[])
        self.conf = self.useFixture(config_fixture.Config(conf))
        ks_client = mock.Mock()
        ks_client.projects.find.return_value = mock.Mock(
            name='gnocchi', id='a2d42c23-d518-46b6-96ab-3fba2e146859')
        self.useFixture(fixtures.MockPatch(
            'ceilometer.keystone_client.get_client',
            return_value=ks_client))
        self.ks_client = ks_client

        self.conf.config(
            resources_definition_file=self.path_get(
                'etc/ceilometer/gnocchi_resources.yaml'),
            group="dispatcher_gnocchi"
        )

        self.sample['resource_id'] = str(uuid.uuid4()) + "_foobar"
        self.sample['message_signature'] = utils.compute_signature(
            self.sample, self.conf.conf.publisher.telemetry_secret)

    @mock.patch('gnocchiclient.v1.client.Client')
    def test_event_workflow(self, fakeclient_cls):
        self.dispatcher = gnocchi.GnocchiDispatcher(self.conf.conf)

        fakeclient = fakeclient_cls.return_value

        fakeclient.resource.search.side_effect = [
            [{"id": "b26268d6-8bb5-11e6-baff-00224d8226cd",
              "type": "instance_disk",
              "instance_id": "9f9d01b9-4a58-4271-9e27-398b21ab20d1"}],
            [{"id": "b1c7544a-8bb5-11e6-850e-00224d8226cd",
              "type": "instance_network_interface",
              "instance_id": "9f9d01b9-4a58-4271-9e27-398b21ab20d1"}],
        ]

        search_params = {
            '=': {'instance_id': '9f9d01b9-4a58-4271-9e27-398b21ab20d1'}
        }

        now = timeutils.utcnow()
        self.useFixture(utils_fixture.TimeFixture(now))

        expected_calls = [
            mock.call.resource.search('instance_disk', search_params),
            mock.call.resource.search('instance_network_interface',
                                      search_params),
            mock.call.resource.update(
                'instance', '9f9d01b9-4a58-4271-9e27-398b21ab20d1',
                {'ended_at': now.isoformat()}),
            mock.call.resource.update(
                'instance_disk',
                'b26268d6-8bb5-11e6-baff-00224d8226cd',
                {'ended_at': now.isoformat()}),
            mock.call.resource.update(
                'instance_network_interface',
                'b1c7544a-8bb5-11e6-850e-00224d8226cd',
                {'ended_at': now.isoformat()}),
            mock.call.resource.update(
                'image', 'dc337359-de70-4044-8e2c-80573ba6e577',
                {'ended_at': now.isoformat()}),
            mock.call.resource.update(
                'volume', '6cc6e7dd-d17d-460f-ae79-7e08a216ce96',
                {'ended_at': now.isoformat()}),
            mock.call.resource.update(
                'network', '705e2c08-08e8-45cb-8673-5c5be955569b',
                {'ended_at': now.isoformat()})
        ]

        self.dispatcher.record_events([INSTANCE_DELETE_START,
                                      IMAGE_DELETE_START,
                                      VOLUME_DELETE_START,
                                      FLOATINGIP_DELETE_END])
        self.assertEqual(8, len(fakeclient.mock_calls))
        for call in expected_calls:
            self.assertIn(call, fakeclient.mock_calls)

    @mock.patch('ceilometer.dispatcher.gnocchi.LOG')
    @mock.patch('gnocchiclient.v1.client.Client')
    def test_workflow(self, fakeclient_cls, logger):
        self.dispatcher = gnocchi.GnocchiDispatcher(self.conf.conf)

        fakeclient = fakeclient_cls.return_value

        resource_id = self.sample['resource_id'].replace("/", "_")
        metric_name = self.sample['counter_name']
        gnocchi_id = uuid.uuid4()

        expected_calls = [
            mock.call.metric.batch_resources_metrics_measures(
                {resource_id: {metric_name: self.measures_attributes}},
                create_metrics=True)
        ]
        expected_debug = [
            mock.call('gnocchi project found: %s',
                      'a2d42c23-d518-46b6-96ab-3fba2e146859'),
        ]

        measures_posted = False
        batch_side_effect = []
        if self.post_measure_fail:
            batch_side_effect += [Exception('boom!')]
        elif not self.resource_exists:
            batch_side_effect += [
                gnocchi_exc.BadRequest(
                    400, {"cause": "Unknown resources",
                          'detail': [{
                              'resource_id': gnocchi_id,
                              'original_resource_id': resource_id}]})]

            attributes = self.postable_attributes.copy()
            attributes.update(self.patchable_attributes)
            attributes['id'] = self.sample['resource_id']
            attributes['metrics'] = dict((metric_name, {})
                                         for metric_name in self.metric_names)
            for k, v in six.iteritems(attributes['metrics']):
                if k == 'disk.root.size':
                    v['unit'] = 'GB'
                    continue
                if k == 'hardware.ipmi.node.power':
                    v['unit'] = 'W'
                    continue
            expected_calls.append(mock.call.resource.create(
                self.resource_type, attributes))

            if self.create_resource_fail:
                fakeclient.resource.create.side_effect = [Exception('boom!')]
            elif self.create_resource_race:
                fakeclient.resource.create.side_effect = [
                    gnocchi_exc.ResourceAlreadyExists(409)]
            else:  # not resource_exists
                expected_debug.append(mock.call(
                    'Resource %s created', self.sample['resource_id']))

            if not self.create_resource_fail:
                expected_calls.append(
                    mock.call.metric.batch_resources_metrics_measures(
                        {resource_id: {metric_name: self.measures_attributes}},
                        create_metrics=True)
                )

                if self.retry_post_measures_fail:
                    batch_side_effect += [Exception('boom!')]
                else:
                    measures_posted = True

        else:
            measures_posted = True

        if measures_posted:
            batch_side_effect += [None]
            expected_debug.append(
                mock.call("%(measures)d measures posted against %(metrics)d "
                          "metrics through %(resources)d resources", dict(
                              measures=len(self.measures_attributes),
                              metrics=1, resources=1))
            )

        if self.patchable_attributes:
            expected_calls.append(mock.call.resource.update(
                self.resource_type, resource_id,
                self.patchable_attributes))
            if self.update_resource_fail:
                fakeclient.resource.update.side_effect = [Exception('boom!')]
            else:
                expected_debug.append(mock.call(
                    'Resource %s updated', self.sample['resource_id']))

        batch = fakeclient.metric.batch_resources_metrics_measures
        batch.side_effect = batch_side_effect

        self.dispatcher.record_metering_data([self.sample])

        # Check that the last log message is the expected one
        if (self.post_measure_fail
                or self.create_resource_fail
                or self.retry_post_measures_fail
                or (self.update_resource_fail and self.patchable_attributes)):
            logger.error.assert_called_with('boom!', exc_info=True)
        else:
            self.assertEqual(0, logger.error.call_count)
        self.assertEqual(expected_calls, fakeclient.mock_calls)
        self.assertEqual(expected_debug, logger.debug.mock_calls)

DispatcherWorkflowTest.generate_scenarios()
