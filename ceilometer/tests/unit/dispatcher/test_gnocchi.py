#
# Copyright 2014 eNovance
#
# Authors: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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

from gnocchiclient import exceptions as gnocchi_exc
import mock
from oslo_config import fixture as config_fixture
from oslo_utils import fileutils
from oslotest import mockpatch
import requests
import six
import testscenarios

from ceilometer.dispatcher import gnocchi
from ceilometer import service as ceilometer_service
from ceilometer.tests import base

load_tests = testscenarios.load_tests_apply_scenarios


@mock.patch('gnocchiclient.v1.client.Client', mock.Mock())
class DispatcherTest(base.BaseTestCase):

    def setUp(self):
        super(DispatcherTest, self).setUp()
        self.conf = self.useFixture(config_fixture.Config())
        ceilometer_service.prepare_service(argv=[], config_files=[])
        self.conf.config(
            resources_definition_file=self.path_get(
                'etc/ceilometer/gnocchi_resources.yaml'),
            group="dispatcher_gnocchi"
        )
        self.resource_id = str(uuid.uuid4())
        self.samples = [{
            'counter_name': 'disk.root.size',
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
            }},
            {
                'counter_name': 'disk.root.size',
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

        ks_client = mock.Mock(auth_token='fake_token')
        ks_client.projects.find.return_value = mock.Mock(
            name='gnocchi', id='a2d42c23-d518-46b6-96ab-3fba2e146859')
        self.useFixture(mockpatch.Patch(
            'ceilometer.keystone_client.get_client',
            return_value=ks_client))
        self.conf.conf.dispatcher_gnocchi.filter_service_activity = True

    def test_config_load(self):
        self.conf.config(filter_service_activity=False,
                         group='dispatcher_gnocchi')
        d = gnocchi.GnocchiDispatcher(self.conf.conf)
        names = [rd.cfg['resource_type'] for rd in d.resources_definition]
        self.assertIn('instance', names)
        self.assertIn('volume', names)

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
                '._process_resource')
    def _do_test_activity_filter(self, expected_samples,
                                 fake_process_resource):

        def assert_samples(resource_id, metric_grouped_samples):
            samples = []
            for metric_name, s in metric_grouped_samples:
                samples.extend(list(s))
            self.assertEqual(expected_samples, samples)

        fake_process_resource.side_effect = assert_samples

        d = gnocchi.GnocchiDispatcher(self.conf.conf)
        d.record_metering_data(self.samples)

        fake_process_resource.assert_called_with(self.resource_id,
                                                 mock.ANY)

    def test_activity_filter_match_project_id(self):
        self.samples[0]['project_id'] = (
            'a2d42c23-d518-46b6-96ab-3fba2e146859')
        self._do_test_activity_filter([self.samples[1]])

    def test_activity_filter_match_swift_event(self):
        self.samples[0]['counter_name'] = 'storage.api.request'
        self.samples[0]['resource_id'] = 'a2d42c23-d518-46b6-96ab-3fba2e146859'
        self._do_test_activity_filter([self.samples[1]])

    def test_activity_filter_nomatch(self):
        self._do_test_activity_filter(self.samples)


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
                'instance', 'disk.root.size', 'disk.ephemeral.size',
                'memory', 'vcpus', 'memory.usage', 'memory.resident',
                'cpu', 'cpu.delta', 'cpu_util', 'vcpus', 'disk.read.requests',
                'disk.read.requests.rate', 'disk.write.requests',
                'disk.write.requests.rate', 'disk.read.bytes',
                'disk.read.bytes.rate', 'disk.write.bytes',
                'disk.write.bytes.rate', 'disk.latency', 'disk.iops',
                'disk.capacity', 'disk.allocation', 'disk.usage'],
            resource_type='instance')),
        ('hardware.ipmi.node.power', dict(
            sample={
                'counter_name': 'hardware.ipmi.node.power',
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

    worflow_scenarios = [
        ('normal_workflow', dict(measure=204, post_resource=None, metric=None,
                                 measure_retry=None, patch_resource=204)),
        ('new_resource', dict(measure=404, post_resource=204, metric=None,
                              measure_retry=204, patch_resource=204)),
        ('new_resource_fail', dict(measure=404, post_resource=500, metric=None,
                                   measure_retry=None, patch_resource=None)),
        ('resource_update_fail', dict(measure=204, post_resource=None,
                                      metric=None, measure_retry=None,
                                      patch_resource=500)),
        ('new_metric', dict(measure=404, post_resource=None, metric=204,
                            measure_retry=204, patch_resource=204)),
        ('new_metric_fail', dict(measure=404, post_resource=None, metric=500,
                                 measure_retry=None, patch_resource=None)),
        ('retry_fail', dict(measure=404, post_resource=409, metric=None,
                            measure_retry=500, patch_resource=None)),
        ('measure_fail', dict(measure=500, post_resource=None, metric=None,
                              measure_retry=None, patch_resource=None)),
    ]

    @classmethod
    def generate_scenarios(cls):
        cls.scenarios = testscenarios.multiply_scenarios(cls.sample_scenarios,
                                                         cls.worflow_scenarios)

    def setUp(self):
        super(DispatcherWorkflowTest, self).setUp()
        self.conf = self.useFixture(config_fixture.Config())
        # Set this explicitly to avoid conflicts with any existing
        # configuration.
        self.conf.config(url='http://localhost:8041',
                         group='dispatcher_gnocchi')
        ks_client = mock.Mock()
        ks_client.projects.find.return_value = mock.Mock(
            name='gnocchi', id='a2d42c23-d518-46b6-96ab-3fba2e146859')
        self.useFixture(mockpatch.Patch(
            'ceilometer.keystone_client.get_client',
            return_value=ks_client))
        self.ks_client = ks_client

        ceilometer_service.prepare_service(argv=[], config_files=[])
        self.conf.config(
            resources_definition_file=self.path_get(
                'etc/ceilometer/gnocchi_resources.yaml'),
            group="dispatcher_gnocchi"
        )

        self.sample['resource_id'] = str(uuid.uuid4()) + "/foobar"

    @mock.patch('ceilometer.dispatcher.gnocchi.LOG')
    @mock.patch('gnocchiclient.v1.client.Client')
    def test_workflow(self, fakeclient_cls, logger):
        self.dispatcher = gnocchi.GnocchiDispatcher(self.conf.conf)

        fakeclient = fakeclient_cls.return_value

        # FIXME(sileht): we don't use urlparse.quote here
        # to ensure / is converted in %2F
        # temporary disabled until we find a solution
        # on gnocchi side. Current gnocchiclient doesn't
        # encode the resource_id
        resource_id = self.sample['resource_id']  # .replace("/", "%2F"),
        metric_name = self.sample['counter_name']

        expected_calls = [
            mock.call.capabilities.list(),
            mock.call.metric.add_measures(metric_name,
                                          self.measures_attributes,
                                          resource_id)]

        add_measures_side_effect = []

        if self.measure == 404 and self.post_resource:
            add_measures_side_effect += [
                gnocchi_exc.ResourceNotFound(404)]
        elif self.measure == 404 and self.metric:
            add_measures_side_effect += [
                gnocchi_exc.MetricNotFound(404)]
        elif self.measure == 500:
            add_measures_side_effect += [Exception('boom!')]

        if self.post_resource:
            attributes = self.postable_attributes.copy()
            attributes.update(self.patchable_attributes)
            attributes['id'] = self.sample['resource_id']
            attributes['metrics'] = dict((metric_name, {})
                                         for metric_name in self.metric_names)
            expected_calls.append(mock.call.resource.create(
                self.resource_type, attributes))
            if self.post_resource == 409:
                fakeclient.resource.create.side_effect = [
                    gnocchi_exc.ResourceAlreadyExists(409)]
            elif self.post_resource == 500:
                fakeclient.resource.create.side_effect = [Exception('boom!')]

        if self.metric:
            expected_calls.append(mock.call.metric.create({
                'name': self.sample['counter_name'],
                'resource_id': resource_id}))
            if self.metric == 409:
                fakeclient.metric.create.side_effect = [
                    gnocchi_exc.NamedMetricAreadyExists(409)]
            elif self.metric == 500:
                fakeclient.metric.create.side_effect = [Exception('boom!')]

        if self.measure_retry:
            expected_calls.append(mock.call.metric.add_measures(
                metric_name,
                self.measures_attributes,
                resource_id))
            if self.measure_retry == 204:
                add_measures_side_effect += [None]
            elif self.measure_retry == 500:
                add_measures_side_effect += [
                    Exception('boom!')]
        else:
            add_measures_side_effect += [None]

        if self.patch_resource and self.patchable_attributes:
            expected_calls.append(mock.call.resource.update(
                self.resource_type, resource_id,
                self.patchable_attributes))
            if self.patch_resource == 500:
                fakeclient.resource.update.side_effect = [Exception('boom!')]

        fakeclient.metric.add_measures.side_effect = add_measures_side_effect

        self.dispatcher.record_metering_data([self.sample])

        # Check that the last log message is the expected one
        if (self.measure == 500 or self.measure_retry == 500 or
                self.metric == 500 or self.post_resource == 500 or
                (self.patch_resource == 500 and self.patchable_attributes)):
            logger.error.assert_called_with('boom!', exc_info=True)
        elif self.patch_resource == 204 and self.patchable_attributes:
            logger.debug.assert_called_with(
                'Resource %s updated', self.sample['resource_id'])
            self.assertEqual(0, logger.error.call_count)
        elif self.measure == 200:
            logger.debug.assert_called_with(
                "Measure posted on metric %s of resource %s",
                self.sample['counter_name'],
                self.sample['resource_id'])
            self.assertEqual(0, logger.error.call_count)

        self.assertEqual(expected_calls, fakeclient.mock_calls)


DispatcherWorkflowTest.generate_scenarios()
