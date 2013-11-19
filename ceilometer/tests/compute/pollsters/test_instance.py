# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
# Copyright © 2012 Red Hat, Inc
#
# Author: Julien Danjou <julien@danjou.info>
# Author: Eoghan Glynn <eglynn@redhat.com>
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

import mock

from ceilometer.compute import manager
from ceilometer.compute.pollsters import instance as pollsters_instance
from ceilometer.tests.compute.pollsters import base


class TestInstancePollster(base.TestPollsterBase):

    def setUp(self):
        super(TestInstancePollster, self).setUp()

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples_instance(self):
        mgr = manager.AgentManager()
        pollster = pollsters_instance.InstancePollster()
        samples = list(pollster.get_samples(mgr, {}, self.instance))
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].name, 'instance')
        self.assertEqual(samples[0].resource_metadata['vcpus'], 1)
        self.assertEqual(samples[0].resource_metadata['memory_mb'], 512)
        self.assertEqual(samples[0].resource_metadata['disk_gb'], 20)
        self.assertEqual(samples[0].resource_metadata['root_gb'], 20)
        self.assertEqual(samples[0].resource_metadata['ephemeral_gb'], 0)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples_instance_flavor(self):
        mgr = manager.AgentManager()
        pollster = pollsters_instance.InstanceFlavorPollster()
        samples = list(pollster.get_samples(mgr, {}, self.instance))
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].name, 'instance:m1.small')
