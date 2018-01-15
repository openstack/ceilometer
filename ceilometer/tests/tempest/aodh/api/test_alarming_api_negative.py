#    Copyright 2015 GlobalLogic.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_utils import uuidutils
from tempest.lib.common.utils import data_utils
from tempest.lib import decorators
from tempest.lib import exceptions as lib_exc

from ceilometer.tests.tempest.aodh.api import base


class TelemetryAlarmingNegativeTest(base.BaseAlarmingTest):
    """Negative tests for show_alarm, update_alarm, show_alarm_history tests

        ** show non-existent alarm
        ** show the deleted alarm
        ** delete deleted alarm
        ** update deleted alarm
    """

    @decorators.attr(type=['negative'])
    @decorators.idempotent_id('668743d5-08ad-4480-b2b8-15da34f81e7e')
    def test_get_non_existent_alarm(self):
        # get the non-existent alarm
        non_existent_id = uuidutils.generate_uuid()
        self.assertRaises(lib_exc.NotFound, self.alarming_client.show_alarm,
                          non_existent_id)

    @decorators.attr(type=['negative'])
    @decorators.idempotent_id('ef45000d-0a72-4781-866d-4cb7bf2582ae')
    def test_get_update_show_history_delete_deleted_alarm(self):
        # get, update and delete the deleted alarm
        alarm_name = data_utils.rand_name('telemetry_alarm')
        rule = {'metrics': ["c0d457b6-957e-41de-a384-d5eb0957de3b"],
                'aggregation_method': 'mean',
                'comparison_operator': 'eq',
                'threshold': 100.0,
                'granularity': 90}
        body = self.alarming_client.create_alarm(
            name=alarm_name,
            type='gnocchi_aggregation_by_metrics_threshold',
            gnocchi_aggregation_by_metrics_threshold_rule=rule)
        alarm_id = body['alarm_id']
        self.alarming_client.delete_alarm(alarm_id)
        # get the deleted alarm
        self.assertRaises(lib_exc.NotFound, self.alarming_client.show_alarm,
                          alarm_id)

        # update the deleted alarm
        updated_alarm_name = data_utils.rand_name('telemetry_alarm_updated')
        updated_rule = {'metrics': ["c0d457b6-957e-41de-a384-d5eb0957de3b"],
                        'comparison_operator': 'eq',
                        'aggregation_method': 'mean',
                        'threshold': 70,
                        'granularity': 50}
        self.assertRaises(
            lib_exc.NotFound, self.alarming_client.update_alarm,
            alarm_id,
            gnocchi_aggregation_by_metrics_threshold_rule=updated_rule,
            name=updated_alarm_name,
            type='gnocchi_aggregation_by_metrics_threshold')
        # delete the deleted alarm
        self.assertRaises(lib_exc.NotFound, self.alarming_client.delete_alarm,
                          alarm_id)
