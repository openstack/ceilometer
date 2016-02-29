#
# Copyright 2015 eNovance
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

from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import timeutils
import requests
import six.moves

from ceilometer.alarm import evaluator
from ceilometer.i18n import _
from ceilometer import keystone_client

LOG = log.getLogger(__name__)

COMPARATORS = {
    'gt': operator.gt,
    'lt': operator.lt,
    'ge': operator.ge,
    'le': operator.le,
    'eq': operator.eq,
    'ne': operator.ne,
}

OPTS = [
    cfg.StrOpt('gnocchi_url',
               default="http://localhost:8041",
               deprecated_for_removal=True,
               help='URL to Gnocchi.'),
]

cfg.CONF.register_opts(OPTS, group="alarms")
cfg.CONF.import_opt('http_timeout', 'ceilometer.service')


class GnocchiThresholdEvaluator(evaluator.Evaluator):

    # the sliding evaluation window is extended to allow
    # for reporting/ingestion lag
    look_back = 1

    # minimum number of datapoints within sliding window to
    # avoid unknown state
    quorum = 1

    def __init__(self, notifier):
        super(GnocchiThresholdEvaluator, self).__init__(notifier)
        self.gnocchi_url = cfg.CONF.alarms.gnocchi_url
        self._ks_client = None

    @property
    def ks_client(self):
        if self._ks_client is None:
            self._ks_client = keystone_client.get_client()
        return self._ks_client

    def _get_headers(self, content_type="application/json"):
        return {
            'Content-Type': content_type,
            'X-Auth-Token': self.ks_client.auth_token,
        }

    def _statistics(self, alarm, start, end):
        """Retrieve statistics over the current window."""
        method = 'get'
        req = {
            'url': self.gnocchi_url + "/v1",
            'headers': self._get_headers(),
            'params': {
                'aggregation': alarm.rule['aggregation_method'],
                'start': start,
                'end': end,
            }
        }

        if alarm.type == 'gnocchi_aggregation_by_resources_threshold':
            method = 'post'
            req['url'] += "/aggregation/resource/%s/metric/%s" % (
                alarm.rule['resource_type'], alarm.rule['metric'])
            req['data'] = alarm.rule['query']

        elif alarm.type == 'gnocchi_aggregation_by_metrics_threshold':
            req['url'] += "/aggregation/metric"
            req['params']['metric'] = alarm.rule['metrics']

        elif alarm.type == 'gnocchi_resources_threshold':
            req['url'] += "/resource/%s/%s/metric/%s/measures" % (
                alarm.rule['resource_type'],
                alarm.rule['resource_id'], alarm.rule['metric'])

        LOG.debug('stats query %s', req['url'])
        try:
            r = getattr(requests, method)(**req)
        except Exception:
            LOG.exception(_('alarm stats retrieval failed'))
            return []
        if r.status_code // 100 != 2:
            LOG.exception(_('alarm stats retrieval failed: %s') % r.text)
            return []
        else:
            return jsonutils.loads(r.text)

    @classmethod
    def _bound_duration(cls, alarm):
        """Bound the duration of the statistics query."""
        now = timeutils.utcnow()
        # when exclusion of weak datapoints is enabled, we extend
        # the look-back period so as to allow a clearer sample count
        # trend to be established
        window = (alarm.rule['granularity'] *
                  (alarm.rule['evaluation_periods'] + cls.look_back))
        start = now - datetime.timedelta(seconds=window)
        LOG.debug('query stats from %(start)s to '
                  '%(now)s', {'start': start, 'now': now})
        return start.isoformat(), now.isoformat()

    def _sufficient(self, alarm, statistics):
        """Check for the sufficiency of the data for evaluation.

        Ensure there is sufficient data for evaluation, transitioning to
        unknown otherwise.
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
        """Create a reason data dictionary for this evaluator type."""
        return {'type': 'threshold', 'disposition': disposition,
                'count': count, 'most_recent': most_recent}

    @classmethod
    def _reason(cls, alarm, statistics, distilled, state):
        """Fabricate reason string."""
        count = len(statistics)
        disposition = 'inside' if state == evaluator.OK else 'outside'
        last = statistics[-1]
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

    @staticmethod
    def _select_best_granularity(alarm, statistics):
        """Return the datapoints that correspond to the alarm granularity"""
        # TODO(sileht): if there's no direct match, but there is an archive
        # policy with granularity that's an even divisor or the period,
        # we could potentially do a mean-of-means (or max-of-maxes or whatever,
        # but not a stddev-of-stddevs).
        return [stats[2] for stats in statistics
                if stats[1] == alarm.rule['granularity']]

    def evaluate(self, alarm):
        if not self.within_time_constraint(alarm):
            LOG.debug('Attempted to evaluate alarm %s, but it is not '
                      'within its time constraint.', alarm.alarm_id)
            return

        start, end = self._bound_duration(alarm)
        statistics = self._statistics(alarm, start, end)
        statistics = self._select_best_granularity(alarm, statistics)

        if self._sufficient(alarm, statistics):
            def _compare(value):
                op = COMPARATORS[alarm.rule['comparison_operator']]
                limit = alarm.rule['threshold']
                LOG.debug('comparing value %(value)s against threshold'
                          ' %(limit)s', {'value': value, 'limit': limit})
                return op(value, limit)

            self._transition(alarm,
                             statistics,
                             list(six.moves.map(_compare, statistics)))
