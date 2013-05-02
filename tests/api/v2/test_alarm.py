# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
#
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
#         Angus Salkeld <asalkeld@redhat.com>
#
# Licensed under the Apache License, Version 2.0 (the 'License'); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
'''Tests alarm operation
'''

import logging

from .base import FunctionalTest

LOG = logging.getLogger(__name__)


class TestListEmptyAlarms(FunctionalTest):

    def test_empty(self):
        data = self.get_json('/alarms')
        self.assertEquals([], data)


class TestAlarms(FunctionalTest):

    def setUp(self):
        super(TestAlarms, self).setUp()

    def test_list_alarms(self):
        data = self.get_json('/alarms')
        self.assertEquals(0, len(data))

    def test_get_alarm(self):
        data = self.get_json('/alarms/1', expect_errors=True)
        self.assertEquals(data.status_int, 400)

    def test_post_alarm(self):
        json = {
            'name': 'added_alarm',
            'counter_name': 'ameter',
            'comparison_operator': 'gt',
            'threshold': 2.0,
            'statistic': 'avg',
        }
        data = self.post_json('/alarms', params=json, expect_errors=True)
        self.assertEquals(data.status_int, 400)

    def test_put_alarm(self):
        json = {
            'name': 'renamed_alarm',
        }
        data = self.put_json('/alarms/1', params=json, expect_errors=True)
        self.assertEquals(data.status_int, 400)

    def test_delete_alarm(self):
        data = self.delete('/alarms/1', expect_errors=True)
        self.assertEquals(data.status_int, 400)
