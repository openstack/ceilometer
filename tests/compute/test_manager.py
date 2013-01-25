# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Tests for ceilometer/agent/manager.py
"""

import datetime
import mock

from stevedore import extension

from ceilometer import nova_client
from ceilometer.compute import manager
from ceilometer import counter
from ceilometer import publish
from ceilometer.tests import base

from ceilometer.openstack.common import cfg


def test_load_plugins():
    mgr = manager.AgentManager()
    assert list(mgr.ext_manager), 'Failed to load any plugins'
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

        def get_counters(self, manager, instance):
            self.counters.append((manager, instance))
            return [self.test_data]

    def faux_notify(self, context, msg, topic, secret, source):
        self.notifications.append((msg, topic, secret, source))

    def setUp(self):
        super(TestRunTasks, self).setUp()
        self.notifications = []
        self.stubs.Set(publish, 'publish_counter', self.faux_notify)
        self.mgr = manager.AgentManager()
        self.mgr.ext_manager = extension.ExtensionManager('fake',
                                                          invoke_on_load=False,
                                                          )
        self.mgr.ext_manager.extensions = [extension.Extension('test',
                                                               None,
                                                               None,
                                                               self.Pollster(),
                                                               ),
                                           ]
        # Set up a fake instance value to be returned by
        # instance_get_all_by_host() so when the manager gets the list
        # of instances to poll we can control the results.
        self.instance = {'name': 'faux',
                         'OS-EXT-STS:vm_state': 'active'}
        stillborn_instance = {'name': 'stillborn',
                              'OS-EXT-STS:vm_state': 'error'}
        self.stubs.Set(nova_client.Client, 'instance_get_all_by_host',
                       lambda *x: [self.instance, stillborn_instance])
        self.mox.ReplayAll()
        # Invoke the periodic tasks to call the pollsters.
        self.mgr.periodic_tasks(None)

    def tearDown(self):
        self.Pollster.counters = []
        super(TestRunTasks, self).tearDown()

    def test_message(self):
        self.assertEqual(len(self.Pollster.counters), 2)
        assert self.Pollster.counters[0][1] is self.instance

    def test_notifications(self):
        actual = self.notifications
        assert list(actual[0]) == [self.Pollster.test_data,
                                   cfg.CONF.metering_topic,
                                   cfg.CONF.metering_secret,
                                   cfg.CONF.counter_source]
