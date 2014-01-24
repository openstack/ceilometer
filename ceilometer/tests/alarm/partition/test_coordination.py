# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc
#
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
"""Tests for ceilometer/alarm/partition/coordination.py
"""
import datetime
import logging
import six
import uuid

import mock
from six import moves

from ceilometer.alarm.partition import coordination
from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common import test
from ceilometer.openstack.common import timeutils
from ceilometer.storage import models


class TestCoordinate(test.BaseTestCase):
    def setUp(self):
        super(TestCoordinate, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        self.test_interval = 120
        self.CONF.set_override('evaluation_interval',
                               self.test_interval,
                               group='alarm')
        self.api_client = mock.Mock()
        self.override_start = datetime.datetime(2012, 7, 2, 10, 45)
        timeutils.utcnow.override_time = self.override_start
        self.partition_coordinator = coordination.PartitionCoordinator()
        self.partition_coordinator.coordination_rpc = mock.Mock()
        #add extra logger to check exception conditions and logged content
        self.output = six.moves.StringIO()
        self.str_handler = logging.StreamHandler(self.output)
        coordination.LOG.logger.addHandler(self.str_handler)

    def tearDown(self):
        super(TestCoordinate, self).tearDown()
        timeutils.utcnow.override_time = None
        # clean up the logger
        coordination.LOG.logger.removeHandler(self.str_handler)
        self.output.close()

    def _no_alarms(self):
        self.api_client.alarms.list.return_value = []

    def _some_alarms(self, count):
        alarm_ids = [str(uuid.uuid4()) for _ in moves.xrange(count)]
        alarms = [self._make_alarm(aid) for aid in alarm_ids]
        self.api_client.alarms.list.return_value = alarms
        return alarm_ids

    def _current_alarms(self):
        return self.api_client.alarms.list.return_value

    def _dump_alarms(self, shave):
        alarms = self.api_client.alarms.list.return_value
        alarms = alarms[:shave]
        alarm_ids = [a.alarm_id for a in alarms]
        self.api_client.alarms.list.return_value = alarms
        return alarm_ids

    def _add_alarms(self, boost):
        new_alarm_ids = [str(uuid.uuid4()) for _ in moves.xrange(boost)]
        alarms = self.api_client.alarms.list.return_value
        for aid in new_alarm_ids:
            alarms.append(self._make_alarm(aid))
        self.api_client.alarms.list.return_value = alarms
        return new_alarm_ids

    @staticmethod
    def _make_alarm(uuid):
        return models.Alarm(name='instance_running_hot',
                            type='threshold',
                            user_id='foobar',
                            project_id='snafu',
                            enabled=True,
                            description='',
                            repeat_actions=False,
                            state='insufficient data',
                            state_timestamp=None,
                            timestamp=None,
                            ok_actions=[],
                            alarm_actions=[],
                            insufficient_data_actions=[],
                            alarm_id=uuid,
                            rule=dict(
                                statistic='avg',
                                comparison_operator='gt',
                                threshold=80.0,
                                evaluation_periods=5,
                                period=60,
                                query=[],
                            ))

    def _advance_time(self, factor):
        delta = datetime.timedelta(seconds=self.test_interval * factor)
        timeutils.utcnow.override_time += delta

    def _younger_by(self, offset):
        return self.partition_coordinator.this.priority + offset

    def _older_by(self, offset):
        return self.partition_coordinator.this.priority - offset

    def _check_mastership(self, expected):
        self.partition_coordinator.check_mastership(self.test_interval,
                                                    self.api_client)
        self.assertEqual(expected, self.partition_coordinator.is_master)

    def _new_partition(self, offset):
        younger = self._younger_by(offset)
        pid = uuid.uuid4()
        self.partition_coordinator.presence(pid, younger)
        return (pid, younger)

    def _check_assignments(self, others, alarm_ids, per_worker,
                           expect_uneffected=[]):
        rpc = self.partition_coordinator.coordination_rpc
        calls = rpc.assign.call_args_list
        return self._check_distribution(others, alarm_ids, per_worker, calls,
                                        expect_uneffected)

    def _check_allocation(self, others, alarm_ids, per_worker):
        rpc = self.partition_coordinator.coordination_rpc
        calls = rpc.allocate.call_args_list
        return self._check_distribution(others, alarm_ids, per_worker, calls)

    def _check_distribution(self, others, alarm_ids, per_worker, calls,
                            expect_uneffected=[]):
        uneffected = [pid for pid, _ in others]
        uneffected.extend(expect_uneffected)
        remainder = list(alarm_ids)
        for call in calls:
            args, _ = call
            target, alarms = args
            self.assertTrue(target in uneffected)
            uneffected.remove(target)
            self.assertEqual(len(alarms), per_worker)
            for aid in alarms:
                self.assertTrue(aid in remainder)
                remainder.remove(aid)
        self.assertEqual(set(uneffected), set(expect_uneffected))
        return remainder

    def _forget_assignments(self, expected_assignments):
        rpc = self.partition_coordinator.coordination_rpc
        self.assertEqual(len(rpc.assign.call_args_list),
                         expected_assignments)
        rpc.reset_mock()

    def test_mastership_not_assumed_during_warmup(self):
        self._no_alarms()

        for _ in moves.xrange(7):
            # still warming up
            self._advance_time(0.25)
            self._check_mastership(False)

        # now warmed up
        self._advance_time(0.25)
        self._check_mastership(True)

    def test_uncontested_mastership_assumed(self):
        self._no_alarms()

        self._advance_time(3)

        self._check_mastership(True)

    def test_contested_mastership_assumed(self):
        self._no_alarms()

        self._advance_time(3)

        for offset in moves.xrange(1, 5):
            younger = self._younger_by(offset)
            self.partition_coordinator.presence(uuid.uuid4(), younger)

        self._check_mastership(True)

    def test_bested_mastership_relinquished(self):
        self._no_alarms()

        self._advance_time(3)

        self._check_mastership(True)

        older = self._older_by(1)
        self.partition_coordinator.presence(uuid.uuid4(), older)

        self._check_mastership(False)

    def _do_test_tie_broken_mastership(self, seed, expect_mastership):
        self._no_alarms()
        self.partition_coordinator.this.uuid = uuid.UUID(int=1)

        self._advance_time(3)

        self._check_mastership(True)

        tied = self.partition_coordinator.this.priority
        self.partition_coordinator.presence(uuid.UUID(int=seed), tied)

        self._check_mastership(expect_mastership)

    def test_tie_broken_mastership_assumed(self):
        self._do_test_tie_broken_mastership(2, True)

    def test_tie_broken_mastership_relinquished(self):
        self._do_test_tie_broken_mastership(0, False)

    def test_fair_distribution(self):
        alarm_ids = self._some_alarms(49)

        self._advance_time(3)

        others = [self._new_partition(i) for i in moves.xrange(1, 5)]

        self._check_mastership(True)

        remainder = self._check_assignments(others, alarm_ids, 10)
        self.assertEqual(set(remainder),
                         set(self.partition_coordinator.assignment))

    def test_rebalance_on_partition_startup(self):
        alarm_ids = self._some_alarms(49)

        self._advance_time(3)

        others = [self._new_partition(i) for i in moves.xrange(1, 5)]

        self._check_mastership(True)

        self. _forget_assignments(4)

        others.append(self._new_partition(5))
        self._check_mastership(True)

        remainder = self._check_assignments(others, alarm_ids, 9)
        self.assertEqual(set(remainder),
                         set(self.partition_coordinator.assignment))

    def test_rebalance_on_partition_staleness(self):
        alarm_ids = self._some_alarms(49)

        self._advance_time(3)

        others = [self._new_partition(i) for i in moves.xrange(1, 5)]

        self._check_mastership(True)

        self. _forget_assignments(4)

        self._advance_time(4)

        stale, _ = others.pop()
        for pid, younger in others:
            self.partition_coordinator.presence(pid, younger)

        self._check_mastership(True)

        remainder = self._check_assignments(others, alarm_ids, 13, [stale])
        self.assertEqual(set(remainder),
                         set(self.partition_coordinator.assignment))

    def test_rebalance_on_sufficient_deletion(self):
        alarm_ids = self._some_alarms(49)

        self._advance_time(3)

        others = [self._new_partition(i) for i in moves.xrange(1, 5)]

        self._check_mastership(True)

        self._forget_assignments(4)

        alarm_ids = self._dump_alarms(len(alarm_ids) / 2)

        self._check_mastership(True)

        remainder = self._check_assignments(others, alarm_ids, 5)
        self.assertEqual(set(remainder),
                         set(self.partition_coordinator.assignment))

    def test_no_rebalance_on_insufficient_deletion(self):
        alarm_ids = self._some_alarms(49)

        self._advance_time(3)

        others = [self._new_partition(i) for i in moves.xrange(1, 5)]

        self._check_mastership(True)

        self._forget_assignments(4)

        alarm_ids = self._dump_alarms(45)

        self._check_mastership(True)

        expect_uneffected = [pid for pid, _ in others]
        self._check_assignments(others, alarm_ids, 10, expect_uneffected)

    def test_no_rebalance_on_creation(self):
        self._some_alarms(49)

        self._advance_time(3)

        others = [self._new_partition(i) for i in moves.xrange(1, 5)]

        self._check_mastership(True)

        self._forget_assignments(4)

        new_alarm_ids = self._add_alarms(8)

        master_assignment = set(self.partition_coordinator.assignment)
        self._check_mastership(True)

        remainder = self._check_allocation(others, new_alarm_ids, 2)
        self.assertEqual(len(remainder), 0)
        self.assertEqual(master_assignment,
                         set(self.partition_coordinator.assignment))

    def test_bail_when_overtaken_in_distribution(self):
        self._some_alarms(49)

        self._advance_time(3)

        for i in moves.xrange(1, 5):
            self._new_partition(i)

        def overtake(*args):
            self._new_partition(-1)

        rpc = self.partition_coordinator.coordination_rpc
        rpc.assign.side_effect = overtake

        self._check_mastership(False)

        self.assertEqual(len(rpc.assign.call_args_list), 1)

    def test_assigned_alarms_no_assignment(self):
        alarms = self.partition_coordinator.assigned_alarms(self.api_client)
        self.assertEqual(len(alarms), 0)

    def test_assigned_alarms_assignment(self):
        alarm_ids = self._some_alarms(6)

        uuid = self.partition_coordinator.this.uuid
        self.partition_coordinator.assign(uuid, alarm_ids)

        alarms = self.partition_coordinator.assigned_alarms(self.api_client)
        self.assertEqual(alarms, self._current_alarms())

    def test_assigned_alarms_allocation(self):
        alarm_ids = self._some_alarms(6)

        uuid = self.partition_coordinator.this.uuid
        self.partition_coordinator.assign(uuid, alarm_ids)

        new_alarm_ids = self._add_alarms(2)
        self.partition_coordinator.allocate(uuid, new_alarm_ids)

        alarms = self.partition_coordinator.assigned_alarms(self.api_client)
        self.assertEqual(alarms, self._current_alarms())

    def test_assigned_alarms_deleted_assignment(self):
        alarm_ids = self._some_alarms(6)

        uuid = self.partition_coordinator.this.uuid
        self.partition_coordinator.assign(uuid, alarm_ids)

        self._dump_alarms(len(alarm_ids) / 2)

        alarms = self.partition_coordinator.assigned_alarms(self.api_client)
        self.assertEqual(alarms, self._current_alarms())

    def test__record_oldest(self):
        # Test when the partition to be recorded is the same as the oldest.
        self.partition_coordinator._record_oldest(
            self.partition_coordinator.oldest, True)
        self.assertIsNone(self.partition_coordinator.oldest)

    def test_check_mastership(self):
        # Test the method exception condition.
        self.partition_coordinator._is_master = mock.Mock(
            side_effect=Exception('Boom!'))
        self.partition_coordinator.check_mastership(10, None)
        self.assertTrue('mastership check failed' in self.output.getvalue())

    def test_report_presence(self):
        self.partition_coordinator.coordination_rpc.presence = mock.Mock(
            side_effect=Exception('Boom!'))
        self.partition_coordinator.report_presence()
        self.assertTrue('presence reporting failed' in self.output.getvalue())

    def test_assigned_alarms(self):
        api_client = mock.MagicMock()
        api_client.alarms = mock.Mock(side_effect=Exception('Boom!'))
        self.partition_coordinator.assignment = ['something']
        self.partition_coordinator.assigned_alarms(api_client)
        self.assertTrue('assignment retrieval failed' in
                        self.output.getvalue())


class TestPartitionIdentity(test.BaseTestCase):
    def setUp(self):
        super(TestPartitionIdentity, self).setUp()
        self.id_1st = coordination.PartitionIdentity(str(uuid.uuid4()), 1)
        self.id_2nd = coordination.PartitionIdentity(str(uuid.uuid4()), 2)

    def test_identity_ops(self):
        self.assertNotEqual(self.id_1st, 'Nothing')
        self.assertNotEqual(self.id_1st, self.id_2nd)
        self.assertTrue(self.id_1st < None)
        self.assertFalse(self.id_1st < 'Nothing')
        self.assertTrue(self.id_2nd > self.id_1st)
