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

from oslotest import base

from ceilometer import service


class _PollsterTestBase(base.BaseTestCase):
    def setUp(self):
        super(_PollsterTestBase, self).setUp()
        self.CONF = service.prepare_service([], [])

    def _test_pollster(self, pollster_class, meter_name,
                       meter_type, meter_unit):

        pollster = pollster_class(self.CONF)

        self.assertEqual(pollster.meter_name, meter_name)
        self.assertEqual(pollster.meter_type, meter_type)
        self.assertEqual(pollster.meter_unit, meter_unit)
