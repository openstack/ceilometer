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
import mock

from ceilometer.tests import base
from ceilometer.energy import kwapi
from ceilometer.central import manager
from ceilometer.openstack.common import context

from keystoneclient import exceptions

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


class TestKwapi(base.TestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestKwapi, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()

    @staticmethod
    def fake_get_kwapi_client(self, ksclient):
        raise exceptions.EndpointNotFound("fake keystone exception")

    def test_endpoint_not_exist(self):
        self.stubs.Set(kwapi._Base, 'get_kwapi_client',
                       self.fake_get_kwapi_client)

        counters = list(kwapi.EnergyPollster().get_counters(self.manager, {}))
        self.assertEqual(len(counters), 0)


class TestEnergyPollster(base.TestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestEnergyPollster, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()
        self.stubs.Set(kwapi._Base, '_iter_probes',
                       self.fake_iter_probes)

    @staticmethod
    def fake_iter_probes(self, ksclient, cache):
        probes = PROBE_DICT['probes']
        for key, value in probes.iteritems():
            probe_dict = value
            probe_dict['id'] = key
            yield probe_dict

    def test_counter(self):
        cache = {}
        counters = list(kwapi.EnergyPollster().get_counters(
            self.manager,
            cache,
        ))
        self.assertEqual(len(counters), 3)
        counters_by_name = dict((c.resource_id, c) for c in counters)
        for name, probe in PROBE_DICT['probes'].items():
            counter = counters_by_name[name]
            expected = datetime.datetime.fromtimestamp(
                probe['timestamp']
            ).isoformat()
            self.assertEqual(counter.timestamp, expected)
            self.assertEqual(counter.volume, probe['kwh'])
            # self.assert_(
            #     any(map(lambda counter: counter.volume == probe['w'],
            #             power_counters)))


class TestEnergyPollsterCache(base.TestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestEnergyPollsterCache, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()

    def test_get_counters_cached(self):
        probe = {'id': 'A'}
        probe.update(PROBE_DICT['probes']['A'])
        cache = {
            kwapi.EnergyPollster.CACHE_KEY_PROBE: [probe],
        }
        self.manager.keystone = mock.Mock()
        pollster = kwapi.EnergyPollster()
        with mock.patch.object(pollster, '_get_probes') as do_not_call:
            do_not_call.side_effect = AssertionError('should not be called')
            counters = list(pollster.get_counters(self.manager, cache))
        self.assertEqual(len(counters), 1)


class TestPowerPollster(base.TestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestPowerPollster, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()
        self.stubs.Set(kwapi._Base, '_iter_probes',
                       self.fake_iter_probes)

    @staticmethod
    def fake_iter_probes(self, ksclient, cache):
        probes = PROBE_DICT['probes']
        for key, value in probes.iteritems():
            probe_dict = value
            probe_dict['id'] = key
            yield probe_dict

    def test_counter(self):
        cache = {}
        counters = list(kwapi.PowerPollster().get_counters(
            self.manager,
            cache,
        ))
        self.assertEqual(len(counters), 3)
        counters_by_name = dict((c.resource_id, c) for c in counters)
        for name, probe in PROBE_DICT['probes'].items():
            counter = counters_by_name[name]
            expected = datetime.datetime.fromtimestamp(
                probe['timestamp']
            ).isoformat()
            self.assertEqual(counter.timestamp, expected)
            self.assertEqual(counter.volume, probe['w'])


class TestPowerPollsterCache(base.TestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestPowerPollsterCache, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()

    def test_get_counters_cached(self):
        probe = {'id': 'A'}
        probe.update(PROBE_DICT['probes']['A'])
        cache = {
            kwapi.PowerPollster.CACHE_KEY_PROBE: [probe],
        }
        self.manager.keystone = mock.Mock()
        pollster = kwapi.PowerPollster()
        with mock.patch.object(pollster, '_get_probes') as do_not_call:
            do_not_call.side_effect = AssertionError('should not be called')
            counters = list(pollster.get_counters(self.manager, cache))
        self.assertEqual(len(counters), 1)
