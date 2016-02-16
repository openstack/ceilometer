#
# Copyright 2014 Red Hat, Inc.
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

import uuid

from oslo_config import cfg
from oslo_log import log
import retrying
import tooz.coordination

from ceilometer.i18n import _LE, _LI, _LW
from ceilometer import utils

LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('backend_url',
               help='The backend URL to use for distributed coordination. If '
                    'left empty, per-deployment central agent and per-host '
                    'compute agent won\'t do workload '
                    'partitioning and will only function correctly if a '
                    'single instance of that service is running.'),
    cfg.FloatOpt('heartbeat',
                 default=1.0,
                 help='Number of seconds between heartbeats for distributed '
                      'coordination.'),
    cfg.FloatOpt('check_watchers',
                 default=10.0,
                 help='Number of seconds between checks to see if group '
                      'membership has changed')

]
cfg.CONF.register_opts(OPTS, group='coordination')


class MemberNotInGroupError(Exception):
    def __init__(self, group_id, members, my_id):
        super(MemberNotInGroupError, self).__init__(_LE(
            'Group ID: %{group_id}s, Members: %{members}s, Me: %{me}s: '
            'Current agent is not part of group and cannot take tasks') %
            {'group_id': group_id, 'members': members, 'me': my_id})


def retry_on_member_not_in_group(exception):
    return isinstance(exception, MemberNotInGroupError)


class PartitionCoordinator(object):
    """Workload partitioning coordinator.

    This class uses the `tooz` library to manage group membership.

    To ensure that the other agents know this agent is still alive,
    the `heartbeat` method should be called periodically.

    Coordination errors and reconnects are handled under the hood, so the
    service using the partition coordinator need not care whether the
    coordination backend is down. The `extract_my_subset` will simply return an
    empty iterable in this case.
    """

    def __init__(self, my_id=None):
        self._coordinator = None
        self._groups = set()
        self._my_id = my_id or str(uuid.uuid4())

    def start(self):
        backend_url = cfg.CONF.coordination.backend_url
        if backend_url:
            try:
                self._coordinator = tooz.coordination.get_coordinator(
                    backend_url, self._my_id)
                self._coordinator.start()
                LOG.info(_LI('Coordination backend started successfully.'))
            except tooz.coordination.ToozError:
                LOG.exception(_LE('Error connecting to coordination backend.'))

    def stop(self):
        if not self._coordinator:
            return

        for group in list(self._groups):
            self.leave_group(group)

        try:
            self._coordinator.stop()
        except tooz.coordination.ToozError:
            LOG.exception(_LE('Error connecting to coordination backend.'))
        finally:
            self._coordinator = None

    def is_active(self):
        return self._coordinator is not None

    def heartbeat(self):
        if self._coordinator:
            if not self._coordinator.is_started:
                # re-connect
                self.start()
            try:
                self._coordinator.heartbeat()
            except tooz.coordination.ToozError:
                LOG.exception(_LE('Error sending a heartbeat to coordination '
                                  'backend.'))

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
        while True:
            try:
                join_req = self._coordinator.join_group(group_id)
                join_req.get()
                LOG.info(_LI('Joined partitioning group %s'), group_id)
                break
            except tooz.coordination.MemberAlreadyExist:
                return
            except tooz.coordination.GroupNotCreated:
                create_grp_req = self._coordinator.create_group(group_id)
                try:
                    create_grp_req.get()
                except tooz.coordination.GroupAlreadyExist:
                    pass
            except tooz.coordination.ToozError:
                LOG.exception(_LE('Error joining partitioning group %s,'
                                  ' re-trying'), group_id)
        self._groups.add(group_id)

    def leave_group(self, group_id):
        if group_id not in self._groups:
            return
        if self._coordinator:
            self._coordinator.leave_group(group_id)
            self._groups.remove(group_id)
            LOG.info(_LI('Left partitioning group %s'), group_id)

    def _get_members(self, group_id):
        if not self._coordinator:
            return [self._my_id]

        while True:
            get_members_req = self._coordinator.get_members(group_id)
            try:
                return get_members_req.get()
            except tooz.coordination.GroupNotCreated:
                self.join_group(group_id)

    @retrying.retry(stop_max_attempt_number=5, wait_random_max=2000,
                    retry_on_exception=retry_on_member_not_in_group)
    def extract_my_subset(self, group_id, iterable, attempt=0):
        """Filters an iterable, returning only objects assigned to this agent.

        We have a list of objects and get a list of active group members from
        `tooz`. We then hash all the objects into buckets and return only
        the ones that hashed into *our* bucket.
        """
        if not group_id:
            return iterable
        if group_id not in self._groups:
            self.join_group(group_id)
        try:
            members = self._get_members(group_id)
            LOG.debug('Members of group: %s, Me: %s', members, self._my_id)
            if self._my_id not in members:
                LOG.warning(_LW('Cannot extract tasks because agent failed to '
                                'join group properly. Rejoining group.'))
                self.join_group(group_id)
                members = self._get_members(group_id)
                if self._my_id not in members:
                    raise MemberNotInGroupError(group_id, members, self._my_id)
            hr = utils.HashRing(members)
            filtered = [v for v in iterable
                        if hr.get_node(str(v)) == self._my_id]
            LOG.debug('My subset: %s', [str(f) for f in filtered])
            return filtered
        except tooz.coordination.ToozError:
            LOG.exception(_LE('Error getting group membership info from '
                              'coordination backend.'))
            return []
