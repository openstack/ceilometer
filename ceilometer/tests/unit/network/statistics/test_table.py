#
# Copyright 2014 NEC Corporation.  All rights reserved.
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

from ceilometer.network.statistics import table
from ceilometer import sample
from ceilometer.tests.unit.network import statistics


class TestTablePollsters(statistics._PollsterTestBase):

    def test_table_pollster(self):
        self._test_pollster(
            table.TablePollster,
            'switch.table',
            sample.TYPE_GAUGE,
            'table')

    def test_table_pollster_active_entries(self):
        self._test_pollster(
            table.TablePollsterActiveEntries,
            'switch.table.active.entries',
            sample.TYPE_GAUGE,
            'entry')

    def test_table_pollster_lookup_packets(self):
        self._test_pollster(
            table.TablePollsterLookupPackets,
            'switch.table.lookup.packets',
            sample.TYPE_GAUGE,
            'packet')

    def test_table_pollster_matched_packets(self):
        self._test_pollster(
            table.TablePollsterMatchedPackets,
            'switch.table.matched.packets',
            sample.TYPE_GAUGE,
            'packet')
