# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
# Copyright © 2013 Intel corp.
# Copyright © 2013 eNovance
#
# Author: Yunhong Jiang <yunhong.jiang@intel.com>
#         Julien Danjou <julien@danjou.info>
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

import abc
import datetime

import mock
import six
from stevedore import extension

from ceilometer.openstack.common.fixture import config
from ceilometer import pipeline
from ceilometer import plugin
from ceilometer import sample
from ceilometer.tests import base
from ceilometer import transformer


default_test_data = sample.Sample(
    name='test',
    type=sample.TYPE_CUMULATIVE,
    unit='',
    volume=1,
    user_id='test',
    project_id='test',
    resource_id='test_run_tasks',
    timestamp=datetime.datetime.utcnow().isoformat(),
    resource_metadata={'name': 'Pollster'},
)


class TestPollster(plugin.PollsterBase):
    test_data = default_test_data

    def get_samples(self, manager, cache, instance=None, resources=[]):
        self.samples.append((manager, instance))
        self.resources.extend(resources)
        return [self.test_data]


class TestPollsterException(TestPollster):
    def get_samples(self, manager, cache, instance=None, resources=[]):
        # Put an instance parameter here so that it can be used
        # by both central manager and compute manager
        # In future, we possibly don't need such hack if we
        # combine the get_samples() function again
        self.samples.append((manager, instance))
        self.resources.extend(resources)
        raise Exception()


@six.add_metaclass(abc.ABCMeta)
class BaseAgentManagerTestCase(base.BaseTestCase):

    class Pollster(TestPollster):
        samples = []
        resources = []
        test_data = default_test_data

    class PollsterAnother(TestPollster):
        samples = []
        resources = []
        test_data = sample.Sample(
            name='testanother',
            type=default_test_data.type,
            unit=default_test_data.unit,
            volume=default_test_data.volume,
            user_id=default_test_data.user_id,
            project_id=default_test_data.project_id,
            resource_id=default_test_data.resource_id,
            timestamp=default_test_data.timestamp,
            resource_metadata=default_test_data.resource_metadata)

    class PollsterException(TestPollsterException):
        samples = []
        resources = []
        test_data = sample.Sample(
            name='testexception',
            type=default_test_data.type,
            unit=default_test_data.unit,
            volume=default_test_data.volume,
            user_id=default_test_data.user_id,
            project_id=default_test_data.project_id,
            resource_id=default_test_data.resource_id,
            timestamp=default_test_data.timestamp,
            resource_metadata=default_test_data.resource_metadata)

    class PollsterExceptionAnother(TestPollsterException):
        samples = []
        resources = []
        test_data = sample.Sample(
            name='testexceptionanother',
            type=default_test_data.type,
            unit=default_test_data.unit,
            volume=default_test_data.volume,
            user_id=default_test_data.user_id,
            project_id=default_test_data.project_id,
            resource_id=default_test_data.resource_id,
            timestamp=default_test_data.timestamp,
            resource_metadata=default_test_data.resource_metadata)

    def setup_pipeline(self):
        self.transformer_manager = transformer.TransformerExtensionManager(
            'ceilometer.transformer',
        )
        self.mgr.pipeline_manager = pipeline.PipelineManager(
            self.pipeline_cfg,
            self.transformer_manager)

    def create_extension_manager(self):
        return extension.ExtensionManager.make_test_instance(
            [
                extension.Extension(
                    'test',
                    None,
                    None,
                    self.Pollster(), ),
                extension.Extension(
                    'testanother',
                    None,
                    None,
                    self.PollsterAnother(), ),
                extension.Extension(
                    'testexception',
                    None,
                    None,
                    self.PollsterException(), ),
                extension.Extension(
                    'testexceptionanother',
                    None,
                    None,
                    self.PollsterExceptionAnother(), ),
            ],
        )

    @abc.abstractmethod
    def create_manager(self):
        """Return subclass specific manager."""

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(BaseAgentManagerTestCase, self).setUp()
        self.mgr = self.create_manager()
        self.mgr.pollster_manager = self.create_extension_manager()
        self.pipeline_cfg = [{
            'name': "test_pipeline",
            'interval': 60,
            'counters': ['test'],
            'resources': ['test://'],
            'transformers': [],
            'publishers': ["test"],
        }, ]
        self.setup_pipeline()
        self.CONF = self.useFixture(config.Config()).conf
        self.CONF.set_override(
            'pipeline_cfg_file',
            self.path_get('etc/ceilometer/pipeline.yaml')
        )

    def tearDown(self):
        self.Pollster.samples = []
        self.PollsterAnother.samples = []
        self.PollsterException.samples = []
        self.PollsterExceptionAnother.samples = []
        self.Pollster.resources = []
        self.PollsterAnother.resources = []
        self.PollsterException.resources = []
        self.PollsterExceptionAnother.resources = []
        super(BaseAgentManagerTestCase, self).tearDown()

    def test_setup_polling_tasks(self):
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(len(polling_tasks), 1)
        self.assertTrue(60 in polling_tasks.keys())
        self.assertEqual(len(polling_tasks[60].resources), 1)
        self.assertEqual(len(polling_tasks[60].resources['test']), 1)
        self.mgr.interval_task(polling_tasks.values()[0])
        pub = self.mgr.pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(pub.samples[0], self.Pollster.test_data)

    def test_setup_polling_tasks_multiple_interval(self):
        self.pipeline_cfg.append({
            'name': "test_pipeline",
            'interval': 10,
            'counters': ['test'],
            'resources': ['test://'],
            'transformers': [],
            'publishers': ["test"],
        })
        self.setup_pipeline()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(len(polling_tasks), 2)
        self.assertTrue(60 in polling_tasks.keys())
        self.assertTrue(10 in polling_tasks.keys())

    def test_setup_polling_tasks_mismatch_counter(self):
        self.pipeline_cfg.append(
            {
                'name': "test_pipeline_1",
                'interval': 10,
                'counters': ['test_invalid'],
                'resources': ['invalid://'],
                'transformers': [],
                'publishers': ["test"],
            })
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(len(polling_tasks), 1)
        self.assertTrue(60 in polling_tasks.keys())

    def test_setup_polling_task_same_interval(self):
        self.pipeline_cfg.append({
            'name': "test_pipeline",
            'interval': 60,
            'counters': ['testanother'],
            'resources': ['testanother://'],
            'transformers': [],
            'publishers': ["test"],
        })
        self.setup_pipeline()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(len(polling_tasks), 1)
        pollsters = polling_tasks.get(60).pollsters
        self.assertEqual(len(pollsters), 2)
        self.assertEqual(len(polling_tasks[60].resources), 2)
        self.assertEqual(len(polling_tasks[60].resources['test']), 1)
        self.assertEqual(len(polling_tasks[60].resources['testanother']), 1)

    def test_interval_exception_isolation(self):
        self.pipeline_cfg = [
            {
                'name': "test_pipeline_1",
                'interval': 10,
                'counters': ['testexceptionanother'],
                'resources': ['test://'],
                'transformers': [],
                'publishers': ["test"],
            },
            {
                'name': "test_pipeline_2",
                'interval': 10,
                'counters': ['testexception'],
                'resources': ['test://'],
                'transformers': [],
                'publishers': ["test"],
            },
        ]
        self.mgr.pipeline_manager = pipeline.PipelineManager(
            self.pipeline_cfg,
            self.transformer_manager)

        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(len(polling_tasks.keys()), 1)
        polling_tasks.get(10)
        self.mgr.interval_task(polling_tasks.get(10))
        pub = self.mgr.pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(pub.samples), 0)

    def test_agent_manager_start(self):
        mgr = self.create_manager()
        mgr.pollster_manager = self.mgr.pollster_manager
        mgr.create_polling_task = mock.MagicMock()
        mgr.tg = mock.MagicMock()
        mgr.start()
        self.assertTrue(mgr.tg.add_timer.called)

    def test_manager_exception_persistency(self):
        self.pipeline_cfg.append({
            'name': "test_pipeline",
            'interval': 60,
            'counters': ['testanother'],
            'transformers': [],
            'publishers': ["test"],
        })
        self.setup_pipeline()
