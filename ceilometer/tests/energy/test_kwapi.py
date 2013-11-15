# -*- coding: utf-8 -*-
#
# Author: François Rossigneux <francois.rossigneux@inria.fr>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import datetime

from keystoneclient import exceptions
import mock

from ceilometer.central import manager
from ceilometer.energy import kwapi
from ceilometer.openstack.common import context
from ceilometer.openstack.common.fixture.mockpatch import PatchObject
from ceilometer.openstack.common import test


PROBE_DICT = {
    "probes": {
        "A": {
            "timestamp": 1357730232.68754,
            "w": 107.3,
            "kwh": 0.001058255421506034
        },
        "B": {
            "timestamp": 1357730232.048158,
            "w": 15.0,
            "kwh": 0.029019045026169896
        },
        "C": {
            "timestamp": 1357730232.223375,
            "w": 95.0,
            "kwh": 0.17361822634312918
        }
    }
}


class TestManager(manager.AgentManager):

    def __init__(self):
        super(TestManager, self).__init__()
        self.keystone = None


class TestKwapi(test.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestKwapi, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()

    @staticmethod
    def fake_get_kwapi_client(ksclient):
        raise exceptions.EndpointNotFound("fake keystone exception")

    def test_endpoint_not_exist(self):
        with PatchObject(kwapi._Base, 'get_kwapi_client',
                         side_effect=self.fake_get_kwapi_client):
            pollster = kwapi.EnergyPollster()
            samples = list(pollster.get_samples(self.manager, {}))

        self.assertEqual(len(samples), 0)


class TestEnergyPollster(test.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestEnergyPollster, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()
        self.useFixture(PatchObject(kwapi._Base, '_iter_probes',
                                    side_effect=self.fake_iter_probes))

    @staticmethod
    def fake_iter_probes(ksclient, cache):
        probes = PROBE_DICT['probes']
        for key, value in probes.iteritems():
            probe_dict = value
            probe_dict['id'] = key
            yield probe_dict

    def test_sample(self):
        cache = {}
        samples = list(kwapi.EnergyPollster().get_samples(
            self.manager,
            cache,
        ))
        self.assertEqual(len(samples), 3)
        samples_by_name = dict((s.resource_id, s) for s in samples)
        for name, probe in PROBE_DICT['probes'].items():
            sample = samples_by_name[name]
            expected = datetime.datetime.fromtimestamp(
                probe['timestamp']
            ).isoformat()
            self.assertEqual(sample.timestamp, expected)
            self.assertEqual(sample.volume, probe['kwh'])
            # self.assert_(
            #     any(map(lambda sample: sample.volume == probe['w'],
            #             power_samples)))


class TestEnergyPollsterCache(test.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestEnergyPollsterCache, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()

    def test_get_samples_cached(self):
        probe = {'id': 'A'}
        probe.update(PROBE_DICT['probes']['A'])
        cache = {
            kwapi.EnergyPollster.CACHE_KEY_PROBE: [probe],
        }
        self.manager.keystone = mock.Mock()
        pollster = kwapi.EnergyPollster()
        with mock.patch.object(pollster, '_get_probes') as do_not_call:
            do_not_call.side_effect = AssertionError('should not be called')
            samples = list(pollster.get_samples(self.manager, cache))
        self.assertEqual(len(samples), 1)


class TestPowerPollster(test.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestPowerPollster, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()
        self.useFixture(PatchObject(kwapi._Base, '_iter_probes',
                                    side_effect=self.fake_iter_probes))

    @staticmethod
    def fake_iter_probes(ksclient, cache):
        probes = PROBE_DICT['probes']
        for key, value in probes.iteritems():
            probe_dict = value
            probe_dict['id'] = key
            yield probe_dict

    def test_sample(self):
        cache = {}
        samples = list(kwapi.PowerPollster().get_samples(
            self.manager,
            cache,
        ))
        self.assertEqual(len(samples), 3)
        samples_by_name = dict((s.resource_id, s) for s in samples)
        for name, probe in PROBE_DICT['probes'].items():
            sample = samples_by_name[name]
            expected = datetime.datetime.fromtimestamp(
                probe['timestamp']
            ).isoformat()
            self.assertEqual(sample.timestamp, expected)
            self.assertEqual(sample.volume, probe['w'])


class TestPowerPollsterCache(test.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestPowerPollsterCache, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()

    def test_get_samples_cached(self):
        probe = {'id': 'A'}
        probe.update(PROBE_DICT['probes']['A'])
        cache = {
            kwapi.PowerPollster.CACHE_KEY_PROBE: [probe],
        }
        self.manager.keystone = mock.Mock()
        pollster = kwapi.PowerPollster()
        with mock.patch.object(pollster, '_get_probes') as do_not_call:
            do_not_call.side_effect = AssertionError('should not be called')
            samples = list(pollster.get_samples(self.manager, cache))
        self.assertEqual(len(samples), 1)
