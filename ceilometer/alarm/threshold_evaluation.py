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

import datetime
import operator

from oslo.config import cfg

from ceilometer.openstack.common import log
from ceilometerclient import client as ceiloclient
from ceilometer.openstack.common.gettextutils import _

LOG = log.getLogger(__name__)

COMPARATORS = {
    'gt': operator.gt,
    'lt': operator.lt,
    'ge': operator.ge,
    'le': operator.le,
    'eq': operator.eq,
    'ne': operator.ne,
}

UNKNOWN = 'insufficient data'
OK = 'ok'
ALARM = 'alarm'


class Evaluator(object):
    """This class implements the basic alarm threshold evaluation
       logic.
    """

    # the sliding evaluation window is extended to allow
    # for reporting/ingestion lag
    look_back = 1

    # minimum number of datapoints within sliding window to
    # avoid unknown state
    quorum = 1

    def __init__(self, notifier=None):
        self.alarms = []
        self.notifier = notifier
        self.api_client = None

    def assign_alarms(self, alarms):
        """Assign alarms to be evaluated."""
        self.alarms = alarms

    @property
    def _client(self):
        """Construct or reuse an authenticated API client."""
        if not self.api_client:
            auth_config = cfg.CONF.service_credentials
            creds = dict(
                os_auth_url=auth_config.os_auth_url,
                os_tenant_name=auth_config.os_tenant_name,
                os_password=auth_config.os_password,
                os_username=auth_config.os_username,
                cacert=auth_config.os_cacert,
                endpoint_type=auth_config.os_endpoint_type,
            )
            self.api_client = ceiloclient.get_client(2, **creds)
        return self.api_client

    @staticmethod
    def _constraints(alarm):
        """Assert the constraints on the statistics query."""
        constraints = []
        for (field, value) in alarm.matching_metadata.iteritems():
            constraints.append(dict(field=field, op='eq', value=value))
        return constraints

    @classmethod
    def _bound_duration(cls, alarm, constraints):
        """Bound the duration of the statistics query."""
        now = datetime.datetime.utcnow()
        window = (alarm.period *
                  (alarm.evaluation_periods + cls.look_back))
        start = now - datetime.timedelta(seconds=window)
        LOG.debug(_('query stats from %(start)s to '
                    '%(now)s') % {'start': start, 'now': now})
        after = dict(field='timestamp', op='ge', value=start.isoformat())
        before = dict(field='timestamp', op='le', value=now.isoformat())
        constraints.extend([before, after])
        return constraints

    @staticmethod
    def _sanitize(alarm, statistics):
        """Sanitize statistics.
           Ultimately this will be the hook for the exclusion of chaotic
           datapoints for example.
        """
        LOG.debug(_('sanitize stats %s') % statistics)
        # in practice statistics are always sorted by period start, not
        # strictly required by the API though
        statistics = statistics[:alarm.evaluation_periods]
        LOG.debug(_('pruned statistics to %d') % len(statistics))
        return statistics

    def _statistics(self, alarm, query):
        """Retrieve statistics over the current window."""
        LOG.debug(_('stats query %s') % query)
        try:
            return self._client.statistics.list(alarm.counter_name,
                                                q=query,
                                                period=alarm.period)
        except Exception:
            LOG.exception(_('alarm stats retrieval failed'))
            return []

    def _refresh(self, alarm, state, reason):
        """Refresh alarm state."""
        try:
            previous = alarm.state
            if previous != state:
                LOG.info(_('alarm %(id)s transitioning to %(state)s because '
                           '%(reason)s') % {'id': alarm.alarm_id,
                                            'state': state,
                                            'reason': reason})

                self._client.alarms.update(alarm.alarm_id, **dict(state=state))
            alarm.state = state
            if self.notifier:
                self.notifier.notify(alarm, previous, reason)
        except Exception:
            # retry will occur naturally on the next evaluation
            # cycle (unless alarm state reverts in the meantime)
            LOG.exception(_('alarm state update failed'))

    def _sufficient(self, alarm, statistics):
        """Ensure there is sufficient data for evaluation,
           transitioning to unknown otherwise.
        """
        sufficient = len(statistics) >= self.quorum
        if not sufficient and alarm.state != UNKNOWN:
            reason = _('%d datapoints are unknown') % alarm.evaluation_periods
            self._refresh(alarm, UNKNOWN, reason)
        return sufficient

    @staticmethod
    def _reason(alarm, statistics, distilled, state):
        """Fabricate reason string."""
        count = len(statistics)
        disposition = 'inside' if state == OK else 'outside'
        last = getattr(statistics[-1], alarm.statistic)
        transition = alarm.state != state
        if transition:
            return (_('Transition to %(state)s due to %(count)d samples'
                      ' %(disposition)s threshold, most recent: %(last)s') %
                    {'state': state, 'count': count,
                     'disposition': disposition, 'last': last})
        return (_('Remaining as %(state)s due to %(count)d samples'
                  ' %(disposition)s threshold, most recent: %(last)s') %
                {'state': state, 'count': count,
                 'disposition': disposition, 'last': last})

    def _transition(self, alarm, statistics, compared):
        """Transition alarm state if necessary.

           The transition rules are currently hardcoded as:

           - transitioning from a known state requires an unequivocal
             set of datapoints

           - transitioning from unknown is on the basis of the most
             recent datapoint if equivocal

           Ultimately this will be policy-driven.
        """
        distilled = all(compared)
        unequivocal = distilled or not any(compared)
        unknown = alarm.state == UNKNOWN
        continuous = alarm.repeat_actions

        if unequivocal:
            state = ALARM if distilled else OK
            reason = self._reason(alarm, statistics, distilled, state)
            if alarm.state != state or continuous:
                self._refresh(alarm, state, reason)
        elif unknown or continuous:
            trending_state = ALARM if compared[-1] else OK
            state = trending_state if unknown else alarm.state
            reason = self._reason(alarm, statistics, distilled, state)
            self._refresh(alarm, state, reason)

    def evaluate(self):
        """Evaluate the alarms assigned to this evaluator."""

        LOG.info(_('initiating evaluation cycle on %d alarms') %
                 len(self.alarms))

        for alarm in self.alarms:

            if not alarm.enabled:
                LOG.debug(_('skipping alarm %s') % alarm.alarm_id)
                continue
            LOG.debug(_('evaluating alarm %s') % alarm.alarm_id)

            query = self._bound_duration(
                alarm,
                self._constraints(alarm)
            )

            statistics = self._sanitize(
                alarm,
                self._statistics(alarm, query)
            )

            if self._sufficient(alarm, statistics):

                def _compare(stat):
                    op = COMPARATORS[alarm.comparison_operator]
                    value = getattr(stat, alarm.statistic)
                    limit = alarm.threshold
                    LOG.debug(_('comparing value %(value)s against threshold'
                                ' %(limit)s') %
                              {'value': value, 'limit': limit})
                    return op(value, limit)

                self._transition(alarm,
                                 statistics,
                                 list(map(_compare, statistics)))
