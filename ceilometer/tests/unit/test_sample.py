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

"""Tests for ceilometer/sample.py"""

import datetime

from ceilometer import sample
from ceilometer.tests import base


class TestSample(base.BaseTestCase):
    SAMPLE = sample.Sample(
        name='cpu',
        type=sample.TYPE_CUMULATIVE,
        unit='ns',
        volume='1234567',
        user_id='56c5692032f34041900342503fecab30',
        project_id='ac9494df2d9d4e709bac378cceabaf23',
        resource_id='1ca738a1-c49c-4401-8346-5c60ebdb03f4',
        timestamp=datetime.datetime(2014, 10, 29, 14, 12, 15, 485877),
        resource_metadata={}
    )

    def test_sample_string_format(self):
        expected = ('<name: cpu, volume: 1234567, '
                    'resource_id: 1ca738a1-c49c-4401-8346-5c60ebdb03f4, '
                    'timestamp: 2014-10-29 14:12:15.485877>')
        self.assertEqual(expected, str(self.SAMPLE))
