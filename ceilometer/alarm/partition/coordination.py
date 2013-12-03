# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc
#
# Authors: Eoghan Glynn <eglynn@redhat.com>
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

import math
import random
import uuid

from ceilometer.alarm import rpc as rpc_alarm
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils


LOG = log.getLogger(__name__)


class PartitionIdentity(object):
    """Representation of a partition's identity for age comparison."""

    def __init__(self, uuid, priority):
        self.uuid = uuid
        self.priority = priority

    def __repr__(self):
        return '%s:%s' % (self.uuid, self.priority)

    def __hash__(self):
        return hash((self.uuid, self.priority))

    def __eq__(self, other):
        if not isinstance(other, PartitionIdentity):
            return False
        return self.priority == other.priority and self.uuid == other.uuid

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if not other:
            return True
        if not isinstance(other, PartitionIdentity):
            return False
        older = self.priority < other.priority
        tie_broken = (self.priority == other.priority and
                      self.uuid < other.uuid)
        return older or tie_broken

    def __gt__(self, other):
        return not (self.__lt__(other) or self.__eq__(other))


class PartitionCoordinator(object):
    """Implements the alarm partition coordination protocol.

    A simple protocol based on AMQP fanout RPC is used.

    All available partitions report their presence periodically.

    The priority of each partition in terms of assuming mastership
    is determined by earliest start-time (with a UUID-based tiebreaker
    in the unlikely event of a time clash).

    A single partition assumes mastership at any given time, taking
    responsibility for allocating the alarms to be evaluated across
    the set of currently available partitions.

    When a partition lifecycle event is detected (i.e. a pre-existing
    partition fails to report its presence, or a new one is started
    up), a complete rebalance of the alarms is initiated.

    Individual alarm lifecycle events, on the other hand, do not
    require a full re-balance. Instead new alarms are allocated as
    they are detected, whereas deleted alarms are initially allowed to
    remain within the allocation (as the individual evaluators are tolerant
    of assigned alarms not existing, and the deleted alarms should be
    randomly distributed over the partitions). However once the number of
    alarms deleted since the last rebalance reaches a certain limit, a
    rebalance will be initiated to maintain equity.

    As presence reports are received, each partition keeps track of the
    oldest partition it currently knows about, allowing an assumption of
    mastership to be aborted if an older partition belatedly reports.
    """

    def __init__(self):
        # uniqueness is based on a combination of starting timestamp
        # and UUID
        self.start = timeutils.utcnow()
        self.this = PartitionIdentity(str(uuid.uuid4()),
                                      float(self.start.strftime('%s.%f')))
        self.oldest = None

        # fan-out RPC
        self.coordination_rpc = rpc_alarm.RPCAlarmPartitionCoordination()

        # state maintained by the master
        self.is_master = False
        self.presence_changed = False
        self.reports = {}
        self.last_alarms = set()
        self.deleted_alarms = set()

        # alarms for evaluation, relevant to all partitions regardless
        # of role
        self.assignment = []

    def _distribute(self, alarms, rebalance):
        """Distribute alarms over known set of evaluators.

        :param alarms: the alarms to distribute
        :param rebalance: true if this is a full rebalance
        :return: true if the distribution completed, false if aborted
        """
        verb = 'assign' if rebalance else 'allocate'
        method = (self.coordination_rpc.assign if rebalance
                  else self.coordination_rpc.allocate)
        LOG.debug(_('triggering %s') % verb)
        LOG.debug(_('known evaluators %s') % self.reports)
        per_evaluator = int(math.ceil(len(alarms) /
                            float(len(self.reports) + 1)))
        LOG.debug(_('per evaluator allocation %s') % per_evaluator)
        # for small distributions (e.g. of newly created alarms)
        # we deliberately skew to non-master evaluators
        evaluators = self.reports.keys()
        random.shuffle(evaluators)
        offset = 0
        for evaluator in evaluators:
            # TODO(eglynn): use pagination in the alarms API to chunk large
            # large allocations
            if self.oldest < self.this:
                LOG.warn(_('%(this)s bailing on distribution cycle '
                           'as older partition detected: %(older)s') %
                         dict(this=self.this, older=self.oldest))
                return False
            allocation = alarms[offset:offset + per_evaluator]
            if allocation:
                LOG.debug(_('%(verb)s-ing %(alloc)s to %(eval)s') %
                          dict(verb=verb, alloc=allocation, eval=evaluator))
                method(evaluator.uuid, allocation)
            offset += per_evaluator
        LOG.debug(_('master taking %s for self') % alarms[offset:])
        if rebalance:
            self.assignment = alarms[offset:]
        else:
            self.assignment.extend(alarms[offset:])
        return True

    def _deletion_requires_rebalance(self, alarms):
        """Track the level of deletion activity since the last full rebalance.

        We delay rebalancing until a certain threshold of deletion activity
        has occurred.

        :param alarms: current set of alarms
        :return: True if the level of alarm deletion since the last rebalance
                 is sufficient so as to require a full rebalance
        """
        deleted_alarms = self.last_alarms - set(alarms)
        LOG.debug(_('newly deleted alarms %s') % deleted_alarms)
        self.deleted_alarms.update(deleted_alarms)
        if len(self.deleted_alarms) > len(alarms) / 5:
            LOG.debug(_('alarm deletion activity requires rebalance'))
            self.deleted_alarms = set()
            return True
        return False

    def _record_oldest(self, partition, stale=False):
        """Check if reported partition is the oldest we know about.

        :param partition: reported partition
        :param stale: true if reported partition detected as stale.
        """
        if stale and self.oldest == partition:
            # current oldest partition detected as stale
            self.oldest = None
        elif not self.oldest:
            # no known oldest partition
            self.oldest = partition
        elif partition < self.oldest:
            # new oldest
            self.oldest = partition

    def _is_master(self, interval):
        """Determine if the current partition is the master."""
        now = timeutils.utcnow()
        if timeutils.delta_seconds(self.start, now) < interval * 2:
            LOG.debug(_('%s still warming up') % self.this)
            return False
        is_master = True
        for partition, last_heard in self.reports.items():
            delta = timeutils.delta_seconds(last_heard, now)
            LOG.debug(_('last heard from %(report)s %(delta)s seconds ago') %
                      dict(report=partition, delta=delta))
            if delta > interval * 2:
                del self.reports[partition]
                self._record_oldest(partition, stale=True)
                LOG.debug(_('%(this)s detects stale evaluator: %(stale)s') %
                          dict(this=self.this, stale=partition))
                self.presence_changed = True
            elif partition < self.this:
                is_master = False
                LOG.info(_('%(this)s sees older potential master: %(older)s')
                         % dict(this=self.this, older=partition))
        LOG.info(_('%(this)s is master?: %(is_master)s') %
                 dict(this=self.this, is_master=is_master))
        return is_master

    def _master_role(self, assuming, api_client):
        """Carry out the master role, initiating a distribution if required.

        :param assuming: true if newly assumed mastership
        :param api_client: the API client to use for alarms.
        :return: True if not overtaken by an older partition
        """
        alarms = [a.alarm_id for a in api_client.alarms.list()]
        created_alarms = list(set(alarms) - self.last_alarms)
        LOG.debug(_('newly created alarms %s') % created_alarms)
        sufficient_deletion = self._deletion_requires_rebalance(alarms)
        if (assuming or sufficient_deletion or self.presence_changed):
            still_ahead = self._distribute(alarms, rebalance=True)
        elif created_alarms:
            still_ahead = self._distribute(list(created_alarms),
                                           rebalance=False)
        else:
            # nothing to distribute, but check anyway if overtaken
            still_ahead = self.this < self.oldest
        self.last_alarms = set(alarms)
        LOG.info(_('%(this)s not overtaken as master? %(still_ahead)s') %
                ({'this': self.this, 'still_ahead': still_ahead}))
        return still_ahead

    def check_mastership(self, eval_interval, api_client):
        """Periodically check if the mastership role should be assumed.

        :param eval_interval: the alarm evaluation interval
        :param api_client: the API client to use for alarms.
        """
        LOG.debug(_('%s checking mastership status') % self.this)
        try:
            assuming = not self.is_master
            self.is_master = (self._is_master(eval_interval) and
                              self._master_role(assuming, api_client))
            self.presence_changed = False
        except Exception:
            LOG.exception(_('mastership check failed'))

    def presence(self, uuid, priority):
        """Accept an incoming report of presence."""
        report = PartitionIdentity(uuid, priority)
        if report != self.this:
            if report not in self.reports:
                self.presence_changed = True
            self._record_oldest(report)
            self.reports[report] = timeutils.utcnow()
            LOG.debug(_('%(this)s knows about %(reports)s') %
                      dict(this=self.this, reports=self.reports))

    def assign(self, uuid, alarms):
        """Accept an incoming alarm assignment."""
        if uuid == self.this.uuid:
            LOG.debug(_('%(this)s got assignment: %(alarms)s') %
                      dict(this=self.this, alarms=alarms))
            self.assignment = alarms

    def allocate(self, uuid, alarms):
        """Accept an incoming alarm allocation."""
        if uuid == self.this.uuid:
            LOG.debug(_('%(this)s got allocation: %(alarms)s') %
                      dict(this=self.this, alarms=alarms))
            self.assignment.extend(alarms)

    def report_presence(self):
        """Report the presence of the current partition."""
        LOG.debug(_('%s reporting presence') % self.this)
        try:
            self.coordination_rpc.presence(self.this.uuid, self.this.priority)
        except Exception:
            LOG.exception(_('presence reporting failed'))

    def assigned_alarms(self, api_client):
        """Return the alarms assigned to the current partition."""
        if not self.assignment:
            LOG.debug(_('%s has no assigned alarms to evaluate') % self.this)
            return []

        try:
            LOG.debug(_('%(this)s alarms for evaluation: %(alarms)s') %
                      dict(this=self.this, alarms=self.assignment))
            return [a for a in api_client.alarms.list(q=[{'field': 'enabled',
                                                          'value': True}])
                    if a.alarm_id in self.assignment]
        except Exception:
            LOG.exception(_('assignment retrieval failed'))
            return []
