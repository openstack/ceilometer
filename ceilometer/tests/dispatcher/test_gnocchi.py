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

import json
import uuid

import mock
from oslo_config import fixture as config_fixture
from oslotest import base
from oslotest import mockpatch
import requests
import six.moves.urllib.parse as urlparse
import tempfile
import testscenarios
import yaml

from ceilometer.dispatcher import gnocchi
from ceilometer import service as ceilometer_service

load_tests = testscenarios.load_tests_apply_scenarios


class json_matcher(object):
    def __init__(self, ref):
        self.ref = ref

    def __eq__(self, obj):
        return self.ref == json.loads(obj)

    def __repr__(self):
        return "<json_matcher \"%s\">" % self.ref


class DispatcherTest(base.BaseTestCase):

    def setUp(self):
        super(DispatcherTest, self).setUp()
        self.conf = self.useFixture(config_fixture.Config())
        ceilometer_service.prepare_service([])
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
                'image_ref_url': 'imageref!',
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
                    'image_ref_url': 'imageref!',
                    'instance_flavor_id': 1234,
                    'display_name': 'myinstance',
                }
            }]

        ks_client = mock.Mock(auth_token='fake_token')
        ks_client.tenants.find.return_value = mock.Mock(
            name='gnocchi', id='a2d42c23-d518-46b6-96ab-3fba2e146859')
        self.useFixture(mockpatch.Patch(
            'ceilometer.keystone_client.get_client',
            return_value=ks_client))

    def test_extensions_load(self):
        self.conf.config(filter_service_activity=False,
                         group='dispatcher_gnocchi')
        d = gnocchi.GnocchiDispatcher(self.conf.conf)
        self.assertIn('instance', d.mgmr.names())
        self.assertIn('volume', d.mgmr.names())

    @mock.patch('ceilometer.dispatcher.gnocchi.GnocchiDispatcher'
                '._process_samples')
    def _do_test_activity_filter(self, expected_samples, fake_process_samples):
        d = gnocchi.GnocchiDispatcher(self.conf.conf)
        d.record_metering_data(self.samples)

        fake_process_samples.assert_called_with(
            mock.ANY, self.resource_id, 'disk.root.size',
            expected_samples, True,
        )

    def test_archive_policy_default(self):
        d = gnocchi.GnocchiDispatcher(self.conf.conf)
        self.assertEqual(d.gnocchi_archive_policy_default, "low")

    def test_archive_policy_map_config(self):
        archive_policy_map = yaml.dump({
            'foo.*': 'low'
        })
        archive_policy_cfg_file = tempfile.NamedTemporaryFile(
            mode='w+b', prefix="foo", suffix=".yaml")
        archive_policy_cfg_file.write(archive_policy_map.encode())
        archive_policy_cfg_file.seek(0)
        self.conf.conf.dispatcher_gnocchi.archive_policy_file = (
            archive_policy_cfg_file.name)
        d = gnocchi.GnocchiDispatcher(self.conf.conf)
        self.assertEqual(
            d.get_archive_policy(
                'foo.disk.rate')['archive_policy_name'], "low")
        archive_policy_cfg_file.close()

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
                    'image_ref_url': 'imageref!',
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
                'memory', 'vcpus', 'memory.usage', 'cpu', 'cpu_util'],
            resource_type='instance')),
    ]

    worflow_scenarios = [
        ('normal_workflow', dict(measure=204, post_resource=None, metric=None,
                                 measure_retry=None, patch_resource=204)),
        ('new_resource', dict(measure=404, post_resource=204, metric=None,
                              measure_retry=204, patch_resource=None)),
        ('new_resource_fail', dict(measure=404, post_resource=500, metric=None,
                                   measure_retry=None, patch_resource=None)),
        ('resource_update_fail', dict(measure=204, post_resource=None,
                                      metric=None, measure_retry=None,
                                      patch_resource=500)),
        ('new_metric', dict(measure=404, post_resource=409, metric=204,
                            measure_retry=204, patch_resource=204)),
        ('new_metric_fail', dict(measure=404, post_resource=409, metric=500,
                                 measure_retry=None, patch_resource=None)),
        ('retry_fail', dict(measure=404, post_resource=409, metric=409,
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
        ks_client = mock.Mock(auth_token='fake_token')
        ks_client.tenants.find.return_value = mock.Mock(
            name='gnocchi', id='a2d42c23-d518-46b6-96ab-3fba2e146859')
        self.useFixture(mockpatch.Patch(
            'ceilometer.keystone_client.get_client',
            return_value=ks_client))

        ceilometer_service.prepare_service([])
        self.dispatcher = gnocchi.GnocchiDispatcher(self.conf.conf)
        self.sample['resource_id'] = str(uuid.uuid4())

    @mock.patch('ceilometer.dispatcher.gnocchi.LOG')
    @mock.patch('ceilometer.dispatcher.gnocchi.requests')
    def test_workflow(self, fake_requests, logger):
        base_url = self.dispatcher.conf.dispatcher_gnocchi.url
        url_params = {
            'url': urlparse.urljoin(base_url, '/v1/resource'),
            'resource_id': self.sample['resource_id'],
            'resource_type': self.resource_type,
            'metric_name': self.sample['counter_name']
        }
        headers = {'Content-Type': 'application/json',
                   'X-Auth-Token': 'fake_token'}

        expected_calls = []
        patch_responses = []
        post_responses = []

        # This is needed to mock Exception in py3
        fake_requests.ConnectionError = requests.ConnectionError

        expected_calls.extend([
            mock.call.session(),
            mock.call.adapters.HTTPAdapter(pool_block=True),
            mock.call.session().mount('http://', mock.ANY),
            mock.call.session().mount('https://', mock.ANY),
            mock.call.session().post(
                "%(url)s/%(resource_type)s/%(resource_id)s/"
                "metric/%(metric_name)s/measures" % url_params,
                headers=headers,
                data=json_matcher(self.measures_attributes))
        ])
        post_responses.append(MockResponse(self.measure))

        if self.post_resource:
            attributes = self.postable_attributes.copy()
            attributes.update(self.patchable_attributes)
            attributes['id'] = self.sample['resource_id']
            attributes['metrics'] = dict((metric_name,
                                          {'archive_policy_name': 'low'})
                                         for metric_name in self.metric_names)
            expected_calls.append(mock.call.session().post(
                "%(url)s/%(resource_type)s" % url_params,
                headers=headers,
                data=json_matcher(attributes)),
            )
            post_responses.append(MockResponse(self.post_resource))

        if self.metric:
            expected_calls.append(mock.call.session().post(
                "%(url)s/%(resource_type)s/%(resource_id)s/metric"
                % url_params,
                headers=headers,
                data=json_matcher({self.sample['counter_name']:
                                   {'archive_policy_name': 'low'}})
            ))
            post_responses.append(MockResponse(self.metric))

        if self.measure_retry:
            expected_calls.append(mock.call.session().post(
                "%(url)s/%(resource_type)s/%(resource_id)s/"
                "metric/%(metric_name)s/measures" % url_params,
                headers=headers,
                data=json_matcher(self.measures_attributes))
            )
            post_responses.append(MockResponse(self.measure_retry))

        if self.patch_resource:
            expected_calls.append(mock.call.session().patch(
                "%(url)s/%(resource_type)s/%(resource_id)s" % url_params,
                headers=headers,
                data=json_matcher(self.patchable_attributes)),
            )
            patch_responses.append(MockResponse(self.patch_resource))

        s = fake_requests.session.return_value
        s.patch.side_effect = patch_responses
        s.post.side_effect = post_responses

        self.dispatcher.record_metering_data([self.sample])

        # Check that the last log message is the expected one
        if self.measure == 500 or self.measure_retry == 500:
            logger.error.assert_called_with(
                "Fail to post measure on metric %s of resource %s "
                "with status: %d: Internal Server Error" %
                (self.sample['counter_name'],
                 self.sample['resource_id'],
                 500))

        elif self.post_resource == 500 or self.patch_resource == 500:
            logger.error.assert_called_with(
                "Resource %s %s failed with status: "
                "%d: Internal Server Error" %
                (self.sample['resource_id'],
                 'update' if self.patch_resource else 'creation',
                 500))
        elif self.metric == 500:
            logger.error.assert_called_with(
                "Fail to create metric %s of resource %s "
                "with status: %d: Internal Server Error" %
                (self.sample['counter_name'],
                 self.sample['resource_id'],
                 500))
        elif self.patch_resource == 204:
            logger.debug.assert_called_with(
                'Resource %s updated', self.sample['resource_id'])
        else:
            logger.debug.assert_called_with(
                "Measure posted on metric %s of resource %s",
                self.sample['counter_name'],
                self.sample['resource_id'])

        self.assertEqual(expected_calls, fake_requests.mock_calls)


DispatcherWorkflowTest.generate_scenarios()
