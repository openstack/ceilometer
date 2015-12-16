# -*- coding: utf-8 -*-
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

from keystoneauth1 import exceptions
import mock
from oslo_context import context
from oslotest import base
from oslotest import mockpatch
import six

from ceilometer.agent import manager
from ceilometer.energy import kwapi


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

ENDPOINT = 'end://point'


class TestManager(manager.AgentManager):

    def __init__(self):
        super(TestManager, self).__init__()
        self._keystone = mock.Mock()


class _BaseTestCase(base.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(_BaseTestCase, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()


class TestKwapi(_BaseTestCase):

    @staticmethod
    def fake_get_kwapi_client(ksclient, endpoint):
        raise exceptions.EndpointNotFound("fake keystone exception")

    def test_endpoint_not_exist(self):
        with mockpatch.PatchObject(kwapi._Base, 'get_kwapi_client',
                                   side_effect=self.fake_get_kwapi_client):
            pollster = kwapi.EnergyPollster()
            samples = list(pollster.get_samples(self.manager, {},
                                                [ENDPOINT]))

        self.assertEqual(0, len(samples))


class TestEnergyPollster(_BaseTestCase):
    pollster_cls = kwapi.EnergyPollster
    unit = 'kwh'

    def setUp(self):
        super(TestEnergyPollster, self).setUp()
        self.useFixture(mockpatch.PatchObject(
            kwapi._Base, '_iter_probes', side_effect=self.fake_iter_probes))

    @staticmethod
    def fake_iter_probes(ksclient, cache, endpoint):
        probes = PROBE_DICT['probes']
        for key, value in six.iteritems(probes):
            probe_dict = value
            probe_dict['id'] = key
            yield probe_dict

    def test_default_discovery(self):
        pollster = kwapi.EnergyPollster()
        self.assertEqual('endpoint:energy', pollster.default_discovery)

    def test_sample(self):
        cache = {}
        samples = list(self.pollster_cls().get_samples(self.manager, cache,
                                                       [ENDPOINT]))
        self.assertEqual(len(PROBE_DICT['probes']), len(samples))
        samples_by_name = dict((s.resource_id, s) for s in samples)
        for name, probe in PROBE_DICT['probes'].items():
            sample = samples_by_name[name]
            expected = datetime.datetime.fromtimestamp(
                probe['timestamp']
            ).isoformat()
            self.assertEqual(expected, sample.timestamp)
            self.assertEqual(probe[self.unit], sample.volume)


class TestPowerPollster(TestEnergyPollster):
    pollster_cls = kwapi.PowerPollster
    unit = 'w'


class TestEnergyPollsterCache(_BaseTestCase):
    pollster_cls = kwapi.EnergyPollster

    def test_get_samples_cached(self):
        probe = {'id': 'A'}
        probe.update(PROBE_DICT['probes']['A'])
        cache = {
            '%s-%s' % (ENDPOINT, self.pollster_cls.CACHE_KEY_PROBE): [probe],
        }
        self.manager._keystone = mock.Mock()
        pollster = self.pollster_cls()
        with mock.patch.object(pollster, '_get_probes') as do_not_call:
            do_not_call.side_effect = AssertionError('should not be called')
            samples = list(pollster.get_samples(self.manager, cache,
                                                [ENDPOINT]))
        self.assertEqual(1, len(samples))


class TestPowerPollsterCache(TestEnergyPollsterCache):
    pollster_cls = kwapi.PowerPollster
