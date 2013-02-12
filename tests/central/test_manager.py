# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Intel Corp.
#
# Author: Lianhao Lu <lianhao.lu@intel.com>
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
"""Tests for ceilometer/central/manager.py
"""

import datetime
import mock
from stevedore import extension

from ceilometer.central import manager
from ceilometer import counter
from ceilometer.tests import base

from ceilometer.openstack.common import cfg
from keystoneclient.v2_0 import client as ksclient


@mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
def test_load_plugins():
    mgr = manager.AgentManager()
    assert list(mgr.pollster_manager), 'Failed to load any plugins'
    return


class TestRunTasks(base.TestCase):

    class Pollster:
        counters = []
        test_data = counter.Counter(
            name='test',
            type=counter.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'Pollster'},
        )

        def get_counters(self, manager):
            self.counters.append((manager, self.test_data))
            return [self.test_data]

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestRunTasks, self).setUp()
        self.stubs.Set(ksclient, 'Client', lambda *args, **kwargs: None)
        self.mgr = manager.AgentManager()

        self.mgr.pollster_manager = extension.ExtensionManager(
            'fake',
            invoke_on_load=False,
        )
        self.mgr.pollster_manager.extensions = [
            extension.Extension('test',
                                None,
                                None,
                                self.Pollster(), ),
        ]
        # Invoke the periodic tasks to call the pollsters.
        self.mgr.periodic_tasks(None)

    def tearDown(self):
        self.Pollster.counters = []
        super(TestRunTasks, self).tearDown()

    def test_message(self):
        self.assertEqual(len(self.Pollster.counters), 1)
        self.assertTrue(self.Pollster.counters[0][1] is
                        self.Pollster.test_data)

    def test_notifications(self):
        self.assertTrue(self.mgr.pipeline_manager.publish_counter.called)
        args, _ = self.mgr.pipeline_manager.publish_counter.call_args
        self.assertEqual(args[1], self.Pollster.test_data)
        self.assertEqual(args[2], cfg.CONF.counter_source)
