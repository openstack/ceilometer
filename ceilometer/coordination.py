#
# Copyright 2014-2017 Red Hat, Inc.
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

import six

from oslo_config import cfg
from oslo_log import log
import tenacity
import tooz.coordination
from tooz import hashring

from ceilometer.i18n import _LE, _LI

LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('backend_url',
               help='The backend URL to use for distributed coordination. If '
                    'left empty, per-deployment central agent and per-host '
                    'compute agent won\'t do workload '
                    'partitioning and will only function correctly if a '
                    'single instance of that service is running.'),
    cfg.FloatOpt('check_watchers',
                 default=10.0,
                 help='Number of seconds between checks to see if group '
                      'membership has changed'),
    cfg.IntOpt('retry_backoff',
               default=1,
               help='Retry backoff factor when retrying to connect with '
                    'coordination backend'),
    cfg.IntOpt('max_retry_interval',
               default=30,
               help='Maximum number of seconds between retry to join '
                    'partitioning group')
]


class PartitionCoordinator(object):
    """Workload partitioning coordinator.

    This class uses the `tooz` library to manage group membership.

    Coordination errors and reconnects are handled under the hood, so the
    service using the partition coordinator need not care whether the
    coordination backend is down. The `extract_my_subset` will simply return an
    empty iterable in this case.
    """

    def __init__(self, conf, my_id):
        self.conf = conf
        self._my_id = my_id
        self._coordinator = tooz.coordination.get_coordinator(
            conf.coordination.backend_url, my_id)

    def start(self):
        try:
            self._coordinator.start(start_heart=True)
            LOG.info(_LI('Coordination backend started successfully.'))
        except tooz.coordination.ToozError:
            LOG.exception(_LE('Error connecting to coordination backend.'))

    def stop(self):
        if not self._coordinator:
            return

        try:
            self._coordinator.stop()
        except tooz.coordination.ToozError:
            LOG.exception(_LE('Error connecting to coordination backend.'))
        finally:
            self._coordinator = None

    def watch_group(self, namespace, callback):
        if self._coordinator:
            self._coordinator.watch_join_group(namespace, callback)
            self._coordinator.watch_leave_group(namespace, callback)

    def run_watchers(self):
        if self._coordinator:
            self._coordinator.run_watchers()

    def join_group(self, group_id):
        if (not self._coordinator or not self._coordinator.is_started
                or not group_id):
            return

        @tenacity.retry(
            wait=tenacity.wait_exponential(
                multiplier=self.conf.coordination.retry_backoff,
                max=self.conf.coordination.max_retry_interval),
            retry=tenacity.retry_never)
        def _inner():
            try:
                self._coordinator.join_group_create(group_id)
            except tooz.coordination.MemberAlreadyExist:
                pass
            except tooz.coordination.ToozError:
                LOG.exception(_LE('Error joining partitioning group %s,'
                                  ' re-trying'), group_id)
                raise tenacity.TryAgain
            LOG.info(_LI('Joined partitioning group %s'), group_id)

        return _inner()

    def _get_members(self, group_id):
        if not self._coordinator:
            return [self._my_id]

        while True:
            get_members_req = self._coordinator.get_members(group_id)
            try:
                return get_members_req.get()
            except tooz.coordination.GroupNotCreated:
                self.join_group(group_id)

    def extract_my_subset(self, group_id, iterable):
        """Filters an iterable, returning only objects assigned to this agent.

        We have a list of objects and get a list of active group members from
        `tooz`. We then hash all the objects into buckets and return only
        the ones that hashed into *our* bucket.
        """
        try:
            members = self._get_members(group_id)
            hr = hashring.HashRing(members, partitions=100)
            iterable = list(iterable)
            filtered = [v for v in iterable
                        if self._my_id in hr.get_nodes(self.encode_task(v))]
            LOG.debug('The universal set: %s, my subset: %s',
                      [six.text_type(f) for f in iterable],
                      [six.text_type(f) for f in filtered])
            return filtered
        except tooz.coordination.ToozError:
            LOG.exception(_LE('Error getting group membership info from '
                              'coordination backend.'))
            return []

    @staticmethod
    def encode_task(value):
        """encode to bytes"""
        return six.text_type(value).encode('utf-8')
