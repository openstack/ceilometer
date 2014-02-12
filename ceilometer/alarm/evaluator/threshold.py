# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc
#
# Author: Eoghan Glynn <eglynn@redhat.com>
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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

from ceilometer.alarm import evaluator
from ceilometer.alarm.evaluator import utils
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils

LOG = log.getLogger(__name__)

COMPARATORS = {
    'gt': operator.gt,
    'lt': operator.lt,
    'ge': operator.ge,
    'le': operator.le,
    'eq': operator.eq,
    'ne': operator.ne,
}


class ThresholdEvaluator(evaluator.Evaluator):

    # the sliding evaluation window is extended to allow
    # for reporting/ingestion lag
    look_back = 1

    # minimum number of datapoints within sliding window to
    # avoid unknown state
    quorum = 1

    @classmethod
    def _bound_duration(cls, alarm, constraints):
        """Bound the duration of the statistics query."""
        now = timeutils.utcnow()
        # when exclusion of weak datapoints is enabled, we extend
        # the look-back period so as to allow a clearer sample count
        # trend to be established
        look_back = (cls.look_back if not alarm.rule.get('exclude_outliers')
                     else alarm.rule['evaluation_periods'])
        window = (alarm.rule['period'] *
                  (alarm.rule['evaluation_periods'] + look_back))
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
        """
        LOG.debug(_('sanitize stats %s') % statistics)
        if alarm.rule.get('exclude_outliers'):
            key = operator.attrgetter('count')
            mean = utils.mean(statistics, key)
            stddev = utils.stddev(statistics, key, mean)
            lower = mean - 2 * stddev
            upper = mean + 2 * stddev
            inliers, outliers = utils.anomalies(statistics, key, lower, upper)
            if outliers:
                LOG.debug(_('excluded weak datapoints with sample counts %s'),
                          [s.count for s in outliers])
                statistics = inliers
            else:
                LOG.debug('no excluded weak datapoints')

        # in practice statistics are always sorted by period start, not
        # strictly required by the API though
        statistics = statistics[-alarm.rule['evaluation_periods']:]
        LOG.debug(_('pruned statistics to %d') % len(statistics))
        return statistics

    def _statistics(self, alarm, query):
        """Retrieve statistics over the current window."""
        LOG.debug(_('stats query %s') % query)
        try:
            return self._client.statistics.list(
                meter_name=alarm.rule['meter_name'], q=query,
                period=alarm.rule['period'])
        except Exception:
            LOG.exception(_('alarm stats retrieval failed'))
            return []

    def _sufficient(self, alarm, statistics):
        """Ensure there is sufficient data for evaluation,
           transitioning to unknown otherwise.
        """
        sufficient = len(statistics) >= self.quorum
        if not sufficient and alarm.state != evaluator.UNKNOWN:
            reason = _('%d datapoints are unknown') % alarm.rule[
                'evaluation_periods']
            reason_data = self._reason_data('unknown',
                                            alarm.rule['evaluation_periods'],
                                            None)
            self._refresh(alarm, evaluator.UNKNOWN, reason, reason_data)
        return sufficient

    @staticmethod
    def _reason_data(disposition, count, most_recent):
        """Create a reason data dictionary for this evaluator type.
        """
        return {'type': 'threshold', 'disposition': disposition,
                'count': count, 'most_recent': most_recent}

    @classmethod
    def _reason(cls, alarm, statistics, distilled, state):
        """Fabricate reason string."""
        count = len(statistics)
        disposition = 'inside' if state == evaluator.OK else 'outside'
        last = getattr(statistics[-1], alarm.rule['statistic'])
        transition = alarm.state != state
        reason_data = cls._reason_data(disposition, count, last)
        if transition:
            return (_('Transition to %(state)s due to %(count)d samples'
                      ' %(disposition)s threshold, most recent:'
                      ' %(most_recent)s')
                    % dict(reason_data, state=state)), reason_data
        return (_('Remaining as %(state)s due to %(count)d samples'
                  ' %(disposition)s threshold, most recent: %(most_recent)s')
                % dict(reason_data, state=state)), reason_data

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
        unknown = alarm.state == evaluator.UNKNOWN
        continuous = alarm.repeat_actions

        if unequivocal:
            state = evaluator.ALARM if distilled else evaluator.OK
            reason, reason_data = self._reason(alarm, statistics,
                                               distilled, state)
            if alarm.state != state or continuous:
                self._refresh(alarm, state, reason, reason_data)
        elif unknown or continuous:
            trending_state = evaluator.ALARM if compared[-1] else evaluator.OK
            state = trending_state if unknown else alarm.state
            reason, reason_data = self._reason(alarm, statistics,
                                               distilled, state)
            self._refresh(alarm, state, reason, reason_data)

    def evaluate(self, alarm):
        query = self._bound_duration(
            alarm,
            alarm.rule['query']
        )

        statistics = self._sanitize(
            alarm,
            self._statistics(alarm, query)
        )

        if self._sufficient(alarm, statistics):
            def _compare(stat):
                op = COMPARATORS[alarm.rule['comparison_operator']]
                value = getattr(stat, alarm.rule['statistic'])
                limit = alarm.rule['threshold']
                LOG.debug(_('comparing value %(value)s against threshold'
                            ' %(limit)s') %
                          {'value': value, 'limit': limit})
                return op(value, limit)

            self._transition(alarm,
                             statistics,
                             map(_compare, statistics))
