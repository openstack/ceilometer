#
# Copyright 2014 Red Hat, Inc.
#
# Author: Nejc Saje <nsaje@redhat.com>
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

import logging
import mock
from oslo.config import fixture as fixture_config
import tooz.coordination

from ceilometer import coordination
from ceilometer.tests import base
from ceilometer import utils


class MockToozCoordinator(object):
    def __init__(self, member_id, shared_storage):
        self._member_id = member_id
        self._groups = shared_storage

    def start(self):
        pass

    def heartbeat(self):
        pass

    def create_group(self, group_id):
        if group_id in self._groups:
            return MockAsyncError(
                tooz.coordination.GroupAlreadyExist(group_id))
        self._groups[group_id] = {}
        return MockAsyncResult(None)

    def join_group(self, group_id, capabilities=b''):
        if group_id not in self._groups:
            return MockAsyncError(
                tooz.coordination.GroupNotCreated(group_id))
        if self._member_id in self._groups[group_id]:
            return MockAsyncError(
                tooz.coordination.MemberAlreadyExist(group_id,
                                                     self._member_id))
        self._groups[group_id][self._member_id] = {
            "capabilities": capabilities,
        }
        return MockAsyncResult(None)

    def get_members(self, group_id):
        if group_id not in self._groups:
            return MockAsyncError(
                tooz.coordination.GroupNotCreated(group_id))
        return MockAsyncResult(self._groups[group_id])


class MockToozCoordExceptionRaiser(MockToozCoordinator):
    def start(self):
        raise tooz.coordination.ToozError('error')

    def heartbeat(self):
        raise tooz.coordination.ToozError('error')

    def join_group(self, group_id, capabilities=b''):
        raise tooz.coordination.ToozError('error')

    def get_members(self, group_id):
        raise tooz.coordination.ToozError('error')


class MockAsyncResult(tooz.coordination.CoordAsyncResult):
    def __init__(self, result):
        self.result = result

    def get(self, timeout=0):
        return self.result

    @staticmethod
    def done():
        return True


class MockAsyncError(tooz.coordination.CoordAsyncResult):
    def __init__(self, error):
        self.error = error

    def get(self, timeout=0):
        raise self.error

    @staticmethod
    def done():
        return True


class MockLoggingHandler(logging.Handler):
    """Mock logging handler to check for expected logs."""

    def __init__(self, *args, **kwargs):
        self.reset()
        logging.Handler.__init__(self, *args, **kwargs)

    def emit(self, record):
        self.messages[record.levelname.lower()].append(record.getMessage())

    def reset(self):
        self.messages = {'debug': [],
                         'info': [],
                         'warning': [],
                         'error': [],
                         'critical': []}


class TestPartitioning(base.BaseTestCase):

    def setUp(self):
        super(TestPartitioning, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.str_handler = MockLoggingHandler()
        coordination.LOG.logger.addHandler(self.str_handler)
        self.shared_storage = {}

    def _get_new_started_coordinator(self, shared_storage, agent_id=None,
                                     coordinator_cls=None):
        coordinator_cls = coordinator_cls or MockToozCoordinator
        self.CONF.set_override('backend_url', 'xxx://yyy',
                               group='coordination')
        with mock.patch('tooz.coordination.get_coordinator',
                        lambda _, member_id:
                        coordinator_cls(member_id, shared_storage)):
            pc = coordination.PartitionCoordinator(agent_id)
            pc.start()
            return pc

    def _usage_simulation(self, *agents_kwargs):
        partition_coordinators = []
        for kwargs in agents_kwargs:
            partition_coordinator = self._get_new_started_coordinator(
                self.shared_storage, kwargs['agent_id'], kwargs.get(
                    'coordinator_cls'))
            partition_coordinator.join_group(kwargs['group_id'])
            partition_coordinators.append(partition_coordinator)

        for i, kwargs in enumerate(agents_kwargs):
            all_resources = kwargs.get('all_resources', [])
            expected_resources = kwargs.get('expected_resources', [])
            actual_resources = partition_coordinators[i].extract_my_subset(
                kwargs['group_id'], all_resources)
            self.assertEqual(expected_resources, actual_resources)

    def test_single_group(self):
        agents = [dict(agent_id='agent1', group_id='group'),
                  dict(agent_id='agent2', group_id='group')]
        self._usage_simulation(*agents)

        self.assertEqual(sorted(self.shared_storage.keys()), ['group'])
        self.assertEqual(sorted(self.shared_storage['group'].keys()),
                         ['agent1', 'agent2'])

    def test_multiple_groups(self):
        agents = [dict(agent_id='agent1', group_id='group1'),
                  dict(agent_id='agent2', group_id='group2')]
        self._usage_simulation(*agents)

        self.assertEqual(sorted(self.shared_storage.keys()), ['group1',
                                                              'group2'])

    def test_partitioning(self):
        all_resources = ['resource_%s' % i for i in range(1000)]
        agents = ['agent_%s' % i for i in range(10)]

        expected_resources = [list() for _ in range(len(agents))]
        hr = utils.HashRing(agents)
        for r in all_resources:
            key = agents.index(hr.get_node(r))
            expected_resources[key].append(r)

        agents_kwargs = []
        for i, agent in enumerate(agents):
            agents_kwargs.append(dict(agent_id=agent,
                                 group_id='group',
                                 all_resources=all_resources,
                                 expected_resources=expected_resources[i]))
        self._usage_simulation(*agents_kwargs)

    def test_coordination_backend_offline(self):
        agents = [dict(agent_id='agent1',
                       group_id='group',
                       all_resources=['res1', 'res2'],
                       expected_resources=[],
                       coordinator_cls=MockToozCoordExceptionRaiser)]
        self._usage_simulation(*agents)
        expected_errors = ['Error getting group membership info from '
                           'coordination backend.',
                           'Error connecting to coordination backend.']
        for e in expected_errors:
            self.assertIn(e, self.str_handler.messages['error'])

    def test_reconnect(self):
        coord = self._get_new_started_coordinator({}, 'a',
                                                  MockToozCoordExceptionRaiser)
        with mock.patch('tooz.coordination.get_coordinator',
                        return_value=MockToozCoordExceptionRaiser('a', {})):
            coord.heartbeat()
        expected_errors = ['Error connecting to coordination backend.',
                           'Error sending a heartbeat to coordination '
                           'backend.']
        for e in expected_errors:
            self.assertIn(e, self.str_handler.messages['error'])

        self.str_handler.messages['error'] = []
        with mock.patch('tooz.coordination.get_coordinator',
                        return_value=MockToozCoordinator('a', {})):
            coord.heartbeat()
        for e in expected_errors:
            self.assertNotIn(e, self.str_handler.messages['error'])
