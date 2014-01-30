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
"""Tests for ceilometer/alarm/evaluator/threshold.py
"""
import datetime
import mock
import uuid

from six import moves

from ceilometer.alarm.evaluator import threshold
from ceilometer.openstack.common import timeutils
from ceilometer.storage import models
from ceilometer.tests.alarm.evaluator import base
from ceilometerclient import exc
from ceilometerclient.v2 import statistics
from oslo.config import cfg


class TestEvaluate(base.TestEvaluatorBase):
    EVALUATOR = threshold.ThresholdEvaluator

    def prepare_alarms(self):
        self.alarms = [
            models.Alarm(name='instance_running_hot',
                         description='instance_running_hot',
                         type='threshold',
                         enabled=True,
                         user_id='foobar',
                         project_id='snafu',
                         alarm_id=str(uuid.uuid4()),
                         state='insufficient data',
                         state_timestamp=None,
                         timestamp=None,
                         insufficient_data_actions=[],
                         ok_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         rule=dict(
                             comparison_operator='gt',
                             threshold=80.0,
                             evaluation_periods=5,
                             statistic='avg',
                             period=60,
                             meter_name='cpu_util',
                             query=[{'field': 'meter',
                                     'op': 'eq',
                                     'value': 'cpu_util'},
                                    {'field': 'resource_id',
                                     'op': 'eq',
                                     'value': 'my_instance'}])
                         ),
            models.Alarm(name='group_running_idle',
                         description='group_running_idle',
                         type='threshold',
                         enabled=True,
                         user_id='foobar',
                         project_id='snafu',
                         state='insufficient data',
                         state_timestamp=None,
                         timestamp=None,
                         insufficient_data_actions=[],
                         ok_actions=[],
                         alarm_actions=[],
                         repeat_actions=False,
                         alarm_id=str(uuid.uuid4()),
                         rule=dict(
                             comparison_operator='le',
                             threshold=10.0,
                             evaluation_periods=4,
                             statistic='max',
                             period=300,
                             meter_name='cpu_util',
                             query=[{'field': 'meter',
                                     'op': 'eq',
                                     'value': 'cpu_util'},
                                    {'field': 'metadata.user_metadata.AS',
                                     'op': 'eq',
                                     'value': 'my_group'}])
                         ),
        ]

    @staticmethod
    def _get_stat(attr, value, count=1):
        return statistics.Statistics(None, {attr: value, 'count': count})

    @staticmethod
    def _reason_data(disposition, count, most_recent):
        return {'type': 'threshold', 'disposition': disposition,
                'count': count, 'most_recent': most_recent}

    def _set_all_rules(self, field, value):
        for alarm in self.alarms:
            alarm.rule[field] = value

    def test_retry_transient_api_failure(self):
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            broken = exc.CommunicationError(message='broken')
            avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] - v)
                    for v in moves.xrange(5)]
            maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] + v)
                    for v in moves.xrange(1, 4)]
            self.api_client.statistics.list.side_effect = [broken,
                                                           broken,
                                                           avgs,
                                                           maxs]
            self._evaluate_all_alarms()
            self._assert_all_alarms('insufficient data')
            self._evaluate_all_alarms()
            self._assert_all_alarms('ok')

    def test_simple_insufficient(self):
        self._set_all_alarms('ok')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            self.api_client.statistics.list.return_value = []
            self._evaluate_all_alarms()
            self._assert_all_alarms('insufficient data')
            expected = [mock.call(alarm.alarm_id, state='insufficient data')
                        for alarm in self.alarms]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)
            expected = [mock.call(
                alarm,
                'ok',
                ('%d datapoints are unknown'
                 % alarm.rule['evaluation_periods']),
                self._reason_data('unknown',
                                  alarm.rule['evaluation_periods'],
                                  None))
                for alarm in self.alarms]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_simple_alarm_trip(self):
        self._set_all_alarms('ok')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] + v)
                    for v in moves.xrange(1, 6)]
            maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                    for v in moves.xrange(4)]
            self.api_client.statistics.list.side_effect = [avgs, maxs]
            self._evaluate_all_alarms()
            self._assert_all_alarms('alarm')
            expected = [mock.call(alarm.alarm_id, state='alarm')
                        for alarm in self.alarms]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)
            reasons = ['Transition to alarm due to 5 samples outside'
                       ' threshold, most recent: %s' % avgs[-1].avg,
                       'Transition to alarm due to 4 samples outside'
                       ' threshold, most recent: %s' % maxs[-1].max]
            reason_datas = [self._reason_data('outside', 5, avgs[-1].avg),
                            self._reason_data('outside', 4, maxs[-1].max)]
            expected = [mock.call(alarm, 'ok', reason, reason_data)
                        for alarm, reason, reason_data
                        in zip(self.alarms, reasons, reason_datas)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_simple_alarm_clear(self):
        self._set_all_alarms('alarm')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] - v)
                    for v in moves.xrange(5)]
            maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] + v)
                    for v in moves.xrange(1, 5)]
            self.api_client.statistics.list.side_effect = [avgs, maxs]
            self._evaluate_all_alarms()
            self._assert_all_alarms('ok')
            expected = [mock.call(alarm.alarm_id, state='ok')
                        for alarm in self.alarms]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)
            reasons = ['Transition to ok due to 5 samples inside'
                       ' threshold, most recent: %s' % avgs[-1].avg,
                       'Transition to ok due to 4 samples inside'
                       ' threshold, most recent: %s' % maxs[-1].max]
            reason_datas = [self._reason_data('inside', 5, avgs[-1].avg),
                            self._reason_data('inside', 4, maxs[-1].max)]
            expected = [mock.call(alarm, 'alarm', reason, reason_data)
                        for alarm, reason, reason_data
                        in zip(self.alarms, reasons, reason_datas)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_equivocal_from_known_state(self):
        self._set_all_alarms('ok')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] + v)
                    for v in moves.xrange(5)]
            maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                    for v in moves.xrange(-1, 3)]
            self.api_client.statistics.list.side_effect = [avgs, maxs]
            self._evaluate_all_alarms()
            self._assert_all_alarms('ok')
            self.assertEqual(self.api_client.alarms.set_state.call_args_list,
                             [])
            self.assertEqual(self.notifier.notify.call_args_list, [])

    def test_equivocal_from_known_state_and_repeat_actions(self):
        self._set_all_alarms('ok')
        self.alarms[1].repeat_actions = True
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] + v)
                    for v in moves.xrange(5)]
            maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                    for v in moves.xrange(-1, 3)]
            self.api_client.statistics.list.side_effect = [avgs, maxs]
            self._evaluate_all_alarms()
            self._assert_all_alarms('ok')
            self.assertEqual(self.api_client.alarms.set_state.call_args_list,
                             [])
            reason = 'Remaining as ok due to 4 samples inside' \
                     ' threshold, most recent: 8.0'
            reason_datas = self._reason_data('inside', 4, 8.0)
            expected = [mock.call(self.alarms[1], 'ok', reason, reason_datas)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_unequivocal_from_known_state_and_repeat_actions(self):
        self._set_all_alarms('alarm')
        self.alarms[1].repeat_actions = True
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] + v)
                    for v in moves.xrange(1, 6)]
            maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                    for v in moves.xrange(4)]
            self.api_client.statistics.list.side_effect = [avgs, maxs]
            self._evaluate_all_alarms()
            self._assert_all_alarms('alarm')
            self.assertEqual(self.api_client.alarms.set_state.call_args_list,
                             [])
            reason = 'Remaining as alarm due to 4 samples outside' \
                     ' threshold, most recent: 7.0'
            reason_datas = self._reason_data('outside', 4, 7.0)
            expected = [mock.call(self.alarms[1], 'alarm',
                                  reason, reason_datas)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_state_change_and_repeat_actions(self):
        self._set_all_alarms('ok')
        self.alarms[0].repeat_actions = True
        self.alarms[1].repeat_actions = True
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] + v)
                    for v in moves.xrange(1, 6)]
            maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                    for v in moves.xrange(4)]
            self.api_client.statistics.list.side_effect = [avgs, maxs]
            self._evaluate_all_alarms()
            self._assert_all_alarms('alarm')
            expected = [mock.call(alarm.alarm_id, state='alarm')
                        for alarm in self.alarms]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)
            reasons = ['Transition to alarm due to 5 samples outside'
                       ' threshold, most recent: %s' % avgs[-1].avg,
                       'Transition to alarm due to 4 samples outside'
                       ' threshold, most recent: %s' % maxs[-1].max]
            reason_datas = [self._reason_data('outside', 5, avgs[-1].avg),
                            self._reason_data('outside', 4, maxs[-1].max)]
            expected = [mock.call(alarm, 'ok', reason, reason_data)
                        for alarm, reason, reason_data
                        in zip(self.alarms, reasons, reason_datas)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_equivocal_from_unknown(self):
        self._set_all_alarms('insufficient data')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            avgs = [self._get_stat('avg', self.alarms[0].rule['threshold'] + v)
                    for v in moves.xrange(1, 6)]
            maxs = [self._get_stat('max', self.alarms[1].rule['threshold'] - v)
                    for v in moves.xrange(4)]
            self.api_client.statistics.list.side_effect = [avgs, maxs]
            self._evaluate_all_alarms()
            self._assert_all_alarms('alarm')
            expected = [mock.call(alarm.alarm_id, state='alarm')
                        for alarm in self.alarms]
            update_calls = self.api_client.alarms.set_state.call_args_list
            self.assertEqual(update_calls, expected)
            reasons = ['Transition to alarm due to 5 samples outside'
                       ' threshold, most recent: %s' % avgs[-1].avg,
                       'Transition to alarm due to 4 samples outside'
                       ' threshold, most recent: %s' % maxs[-1].max]
            reason_datas = [self._reason_data('outside', 5, avgs[-1].avg),
                            self._reason_data('outside', 4, maxs[-1].max)]
            expected = [mock.call(alarm, 'insufficient data',
                                  reason, reason_data)
                        for alarm, reason, reason_data
                        in zip(self.alarms, reasons, reason_datas)]
            self.assertEqual(self.notifier.notify.call_args_list, expected)

    def _do_test_bound_duration(self, start, exclude_outliers=None):
        alarm = self.alarms[0]
        if exclude_outliers is not None:
            alarm.rule['exclude_outliers'] = exclude_outliers
        timeutils.utcnow.override_time = datetime.datetime(2012, 7, 2, 10, 45)
        constraint = self.evaluator._bound_duration(alarm, [])
        self.assertEqual(constraint, [
            {'field': 'timestamp',
             'op': 'le',
             'value': timeutils.utcnow().isoformat()},
            {'field': 'timestamp',
             'op': 'ge',
             'value': start},
        ])

    def test_bound_duration_outlier_exclusion_defaulted(self):
        self._do_test_bound_duration('2012-07-02T10:39:00')

    def test_bound_duration_outlier_exclusion_clear(self):
        self._do_test_bound_duration('2012-07-02T10:39:00', False)

    def test_bound_duration_outlier_exclusion_set(self):
        self._do_test_bound_duration('2012-07-02T10:35:00', True)

    def test_threshold_endpoint_types(self):
        endpoint_types = ["internalURL", "publicURL"]
        for endpoint_type in endpoint_types:
            cfg.CONF.set_override('os_endpoint_type',
                                  endpoint_type,
                                  group='service_credentials')
            with mock.patch('ceilometerclient.client.get_client') as client:
                self.evaluator.api_client = None
                self._evaluate_all_alarms()
                conf = cfg.CONF.service_credentials
                expected = [mock.call(2,
                                      os_auth_url=conf.os_auth_url,
                                      os_region_name=conf.os_region_name,
                                      os_tenant_name=conf.os_tenant_name,
                                      os_password=conf.os_password,
                                      os_username=conf.os_username,
                                      os_cacert=conf.os_cacert,
                                      os_endpoint_type=conf.os_endpoint_type)]
                actual = client.call_args_list
                self.assertEqual(actual, expected)

    def _do_test_simple_alarm_trip_outlier_exclusion(self, exclude_outliers):
        self._set_all_rules('exclude_outliers', exclude_outliers)
        self._set_all_alarms('ok')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            # most recent datapoints inside threshold but with
            # anomolously low sample count
            threshold = self.alarms[0].rule['threshold']
            avgs = [self._get_stat('avg',
                                   threshold + (v if v < 10 else -v),
                                   count=20 if v < 10 else 1)
                    for v in xrange(1, 11)]
            threshold = self.alarms[1].rule['threshold']
            maxs = [self._get_stat('max',
                                   threshold - (v if v < 7 else -v),
                                   count=20 if v < 7 else 1)
                    for v in xrange(8)]
            self.api_client.statistics.list.side_effect = [avgs, maxs]
            self._evaluate_all_alarms()
            self._assert_all_alarms('alarm' if exclude_outliers else 'ok')
            if exclude_outliers:
                expected = [mock.call(alarm.alarm_id, state='alarm')
                            for alarm in self.alarms]
                update_calls = self.api_client.alarms.set_state.call_args_list
                self.assertEqual(update_calls, expected)
                reasons = ['Transition to alarm due to 5 samples outside'
                           ' threshold, most recent: %s' % avgs[-2].avg,
                           'Transition to alarm due to 4 samples outside'
                           ' threshold, most recent: %s' % maxs[-2].max]
                reason_datas = [self._reason_data('outside', 5, avgs[-2].avg),
                                self._reason_data('outside', 4, maxs[-2].max)]
                expected = [mock.call(alarm, 'ok', reason, reason_data)
                            for alarm, reason, reason_data
                            in zip(self.alarms, reasons, reason_datas)]
                self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_simple_alarm_trip_with_outlier_exclusion(self):
        self. _do_test_simple_alarm_trip_outlier_exclusion(True)

    def test_simple_alarm_no_trip_without_outlier_exclusion(self):
        self. _do_test_simple_alarm_trip_outlier_exclusion(False)

    def _do_test_simple_alarm_clear_outlier_exclusion(self, exclude_outliers):
        self._set_all_rules('exclude_outliers', exclude_outliers)
        self._set_all_alarms('alarm')
        with mock.patch('ceilometerclient.client.get_client',
                        return_value=self.api_client):
            # most recent datapoints outside threshold but with
            # anomolously low sample count
            threshold = self.alarms[0].rule['threshold']
            avgs = [self._get_stat('avg',
                                   threshold - (v if v < 9 else -v),
                                   count=20 if v < 9 else 1)
                    for v in xrange(10)]
            threshold = self.alarms[1].rule['threshold']
            maxs = [self._get_stat('max',
                                   threshold + (v if v < 8 else -v),
                                   count=20 if v < 8 else 1)
                    for v in xrange(1, 9)]
            self.api_client.statistics.list.side_effect = [avgs, maxs]
            self._evaluate_all_alarms()
            self._assert_all_alarms('ok' if exclude_outliers else 'alarm')
            if exclude_outliers:
                expected = [mock.call(alarm.alarm_id, state='ok')
                            for alarm in self.alarms]
                update_calls = self.api_client.alarms.set_state.call_args_list
                self.assertEqual(update_calls, expected)
                reasons = ['Transition to ok due to 5 samples inside'
                           ' threshold, most recent: %s' % avgs[-2].avg,
                           'Transition to ok due to 4 samples inside'
                           ' threshold, most recent: %s' % maxs[-2].max]
                reason_datas = [self._reason_data('inside', 5, avgs[-2].avg),
                                self._reason_data('inside', 4, maxs[-2].max)]
                expected = [mock.call(alarm, 'alarm', reason, reason_data)
                            for alarm, reason, reason_data
                            in zip(self.alarms, reasons, reason_datas)]
                self.assertEqual(self.notifier.notify.call_args_list, expected)

    def test_simple_alarm_clear_with_outlier_exclusion(self):
        self. _do_test_simple_alarm_clear_outlier_exclusion(True)

    def test_simple_alarm_no_clear_without_outlier_exclusion(self):
        self. _do_test_simple_alarm_clear_outlier_exclusion(False)
