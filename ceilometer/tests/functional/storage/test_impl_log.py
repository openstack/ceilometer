#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
"""Tests for ceilometer/storage/impl_log.py
"""
from oslotest import base

from ceilometer.storage import impl_log


class ConnectionTest(base.BaseTestCase):
    @staticmethod
    def test_get_connection():
        conn = impl_log.Connection(None, None)
        conn.record_metering_data({'counter_name': 'test',
                                   'resource_id': __name__,
                                   'counter_volume': 1,
                                   })
