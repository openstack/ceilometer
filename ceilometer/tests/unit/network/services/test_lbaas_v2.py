#
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

import fixtures
import mock
from oslotest import base

from ceilometer.agent import manager
from ceilometer.agent import plugin_base
from ceilometer.network.services import discovery
from ceilometer.network.services import lbaas
from ceilometer import service


class _BaseTestLBPollster(base.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(_BaseTestLBPollster, self).setUp()
        self.addCleanup(mock.patch.stopall)
        self.CONF = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, self.CONF)
        plugin_base._get_keystone = mock.Mock()
        catalog = (plugin_base._get_keystone.session.auth.get_access.
                   return_value.service_catalog)
        catalog.get_endpoints = mock.MagicMock(
            return_value={'network': mock.ANY})


class TestLBListenerPollster(_BaseTestLBPollster):

    def setUp(self):
        super(TestLBListenerPollster, self).setUp()
        self.pollster = lbaas.LBListenerPollster(self.CONF)
        self.pollster.lb_version = 'v2'
        fake_listeners = self.fake_list_listeners()
        self.useFixture(fixtures.MockPatch('ceilometer.neutron_client.Client.'
                                           'list_listener',
                                           return_value=fake_listeners))

    @staticmethod
    def fake_list_listeners():
        return [{'default_pool_id': None,
                 'protocol': 'HTTP',
                 'description': '',
                 'loadbalancers': [
                     {'id': 'a9729389-6147-41a3-ab22-a24aed8692b2'}],
                 'id': '35cb8516-1173-4035-8dae-0dae3453f37f',
                 'name': 'mylistener_online',
                 'admin_state_up': True,
                 'connection_limit': 100,
                 'tenant_id': '3e4d8bec50a845fcb09e03a4375c691d',
                 'protocol_port': 80,
                 'operating_status': 'ONLINE'},
                {'default_pool_id': None,
                 'protocol': 'HTTP',
                 'description': '',
                 'loadbalancers': [
                     {'id': 'ce73ad36-437d-4c84-aee1-186027d3da9a'}],
                 'id': 'cd6a6fee-e2fa-4e6c-b3c2-bfbe395752c1',
                 'name': 'mylistener_offline',
                 'admin_state_up': True,
                 'connection_limit': 100,
                 'tenant_id': '3e4d8bec50a845fcb09e03a4375c691d',
                 'protocol_port': 80,
                 'operating_status': 'OFFLINE'},
                {'default_pool_id': None,
                 'protocol': 'HTTP',
                 'description': '',
                 'loadbalancers': [
                     {'id': 'fe7rad36-437d-4c84-aee1-186027d3bdcd'}],
                 'id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'name': 'mylistener_error',
                 'admin_state_up': True,
                 'connection_limit': 100,
                 'tenant_id': '3e4d8bec50a845fcb09e03a4375c691d',
                 'protocol_port': 80,
                 'operating_status': 'ERROR'},
                {'default_pool_id': None,
                 'protocol': 'HTTP',
                 'description': '',
                 'loadbalancers': [
                     {'id': 'fe7rad36-437d-4c84-aee1-186027d3bdcd'}],
                 'id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'name': 'mylistener_pending_create',
                 'admin_state_up': True,
                 'connection_limit': 100,
                 'tenant_id': '3e4d8bec50a845fcb09e03a4375c691d',
                 'protocol_port': 80,
                 'operating_status': 'PENDING_CREATE'}
                ]

    def test_listener_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_list_listeners()))
        self.assertEqual(3, len(samples))
        for field in self.pollster.FIELDS:
            self.assertEqual(self.fake_list_listeners()[0][field],
                             samples[0].resource_metadata[field])

    def test_listener_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_list_listeners()))
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(0, samples[1].volume)
        self.assertEqual(4, samples[2].volume)

    def test_list_listener_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_list_listeners()))
        self.assertEqual(set(['network.services.lb.listener']),
                         set([s.name for s in samples]))

    def test_listener_discovery(self):
        discovered_listeners = discovery.LBListenersDiscovery(
            self.CONF).discover(self.manager)
        self.assertEqual(4, len(discovered_listeners))
        for listener in self.fake_list_listeners():
            if listener['operating_status'] == 'pending_create':
                self.assertNotIn(listener, discovered_listeners)
            else:
                self.assertIn(listener, discovered_listeners)


class TestLBLoadBalancerPollster(_BaseTestLBPollster):

    def setUp(self):
        super(TestLBLoadBalancerPollster, self).setUp()
        self.pollster = lbaas.LBLoadBalancerPollster(self.CONF)
        self.pollster.lb_version = 'v2'
        fake_loadbalancers = self.fake_list_loadbalancers()
        self.useFixture(fixtures.MockPatch('ceilometer.neutron_client.Client.'
                                           'list_loadbalancer',
                                           return_value=fake_loadbalancers))

    @staticmethod
    def fake_list_loadbalancers():
        return [{'operating_status': 'ONLINE',
                 'description': '',
                 'admin_state_up': True,
                 'tenant_id': '1a3e005cf9ce40308c900bcb08e5320c',
                 'provisioning_status': 'ACTIVE',
                 'listeners': [{'id': 'fe7rad36-437d-4c84-aee1-186027d3bdcd'}],
                 'vip_address': '10.0.0.2',
                 'vip_subnet_id': '013d3059-87a4-45a5-91e9-d721068ae0b2',
                 'id': 'cd6a6fee-e2fa-4e6c-b3c2-bfbe395752c1',
                 'name': 'loadbalancer_online'},
                {'operating_status': 'OFFLINE',
                 'description': '',
                 'admin_state_up': True,
                 'tenant_id': '1a3e005cf9ce40308c900bcb08e5320c',
                 'provisioning_status': 'INACTIVE',
                 'listeners': [{'id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a'}],
                 'vip_address': '10.0.0.3',
                 'vip_subnet_id': 'ce73ad36-437d-4c84-aee1-186027d3da9a',
                 'id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'name': 'loadbalancer_offline'},
                {'operating_status': 'ERROR',
                 'description': '',
                 'admin_state_up': True,
                 'tenant_id': '1a3e005cf9ce40308c900bcb08e5320c',
                 'provisioning_status': 'INACTIVE',
                 'listeners': [{'id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d8b'}],
                 'vip_address': '10.0.0.4',
                 'vip_subnet_id': '213d3059-87a4-45a5-91e9-d721068df0b2',
                 'id': 'cd6a6fee-e2fa-4e6c-b3c2-bfbe395752c1',
                 'name': 'loadbalancer_error'},
                {'operating_status': 'PENDING_CREATE',
                 'description': '',
                 'admin_state_up': True,
                 'tenant_id': '1a3e005cf9ce40308c900bcb08e5320c',
                 'provisioning_status': 'INACTIVE',
                 'listeners': [{'id': 'fe7rad36-437d-4c84-aee1-186027d4ed7c'}],
                 'vip_address': '10.0.0.5',
                 'vip_subnet_id': '123d3059-87a4-45a5-91e9-d721068ae0c3',
                 'id': 'cd6a6fee-e2fa-4e6c-b3c2-bfbe395763b2',
                 'name': 'loadbalancer_pending_create'}
                ]

    def test_loadbalancer_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_list_loadbalancers()))
        self.assertEqual(3, len(samples))
        for field in self.pollster.FIELDS:
            self.assertEqual(self.fake_list_loadbalancers()[0][field],
                             samples[0].resource_metadata[field])

    def test_loadbalancer_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_list_loadbalancers()))
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(0, samples[1].volume)
        self.assertEqual(4, samples[2].volume)

    def test_list_loadbalancer_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_list_loadbalancers()))
        self.assertEqual(set(['network.services.lb.loadbalancer']),
                         set([s.name for s in samples]))

    def test_loadbalancer_discovery(self):
        discovered_loadbalancers = discovery.LBLoadBalancersDiscovery(
            self.CONF).discover(self.manager)
        self.assertEqual(4, len(discovered_loadbalancers))
        for loadbalancer in self.fake_list_loadbalancers():
            if loadbalancer['operating_status'] == 'pending_create':
                self.assertNotIn(loadbalancer, discovered_loadbalancers)
            else:
                self.assertIn(loadbalancer, discovered_loadbalancers)


class TestLBStatsPollster(_BaseTestLBPollster):

    def setUp(self):
        super(TestLBStatsPollster, self).setUp()
        fake_balancer_stats = self.fake_balancer_stats()
        self.useFixture(fixtures.MockPatch('ceilometer.neutron_client.Client.'
                                           'get_loadbalancer_stats',
                                           return_value=fake_balancer_stats))

        fake_loadbalancers = self.fake_list_loadbalancers()
        self.useFixture(fixtures.MockPatch('ceilometer.neutron_client.Client.'
                                           'list_loadbalancer',
                                           return_value=fake_loadbalancers))
        self.CONF.set_override('neutron_lbaas_version',
                               'v2',
                               group='service_types')

    @staticmethod
    def fake_list_loadbalancers():
        return [{'operating_status': 'ONLINE',
                 'description': '',
                 'admin_state_up': True,
                 'tenant_id': '1a3e005cf9ce40308c900bcb08e5320c',
                 'provisioning_status': 'ACTIVE',
                 'listeners': [{'id': 'fe7rad36-437d-4c84-aee1-186027d3bdcd'}],
                 'vip_address': '10.0.0.2',
                 'vip_subnet_id': '013d3059-87a4-45a5-91e9-d721068ae0b2',
                 'id': 'cd6a6fee-e2fa-4e6c-b3c2-bfbe395752c1',
                 'name': 'loadbalancer_online'},
                ]

    @staticmethod
    def fake_balancer_stats():
        return {'active_connections': 2,
                'bytes_in': 1,
                'bytes_out': 3,
                'total_connections': 4}

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def _check_get_samples(self, factory, sample_name, expected_volume,
                           expected_type):
        pollster = factory(self.CONF)

        cache = {}
        samples = list(pollster.get_samples(self.manager, cache,
                                            self.fake_list_loadbalancers()))
        self.assertEqual(1, len(samples))
        self.assertIsNotNone(samples)
        self.assertIn('lbstats', cache)
        self.assertEqual(set([sample_name]), set([s.name for s in samples]))

        match = [s for s in samples if s.name == sample_name]
        self.assertEqual(1, len(match), 'missing counter %s' % sample_name)
        self.assertEqual(expected_volume, match[0].volume)
        self.assertEqual(expected_type, match[0].type)

    def test_lb_total_connections(self):
        self._check_get_samples(lbaas.LBTotalConnectionsPollster,
                                'network.services.lb.total.connections',
                                4, 'cumulative')

    def test_lb_active_connections(self):
        self._check_get_samples(lbaas.LBActiveConnectionsPollster,
                                'network.services.lb.active.connections',
                                2, 'gauge')

    def test_lb_incoming_bytes(self):
        self._check_get_samples(lbaas.LBBytesInPollster,
                                'network.services.lb.incoming.bytes',
                                1, 'gauge')

    def test_lb_outgoing_bytes(self):
        self._check_get_samples(lbaas.LBBytesOutPollster,
                                'network.services.lb.outgoing.bytes',
                                3, 'gauge')
