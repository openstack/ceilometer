#
# Copyright 2016 IBM Corp.
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
import copy
import datetime

from oslo_utils import timeutils
from oslotest import base

from ceilometer import sample
from ceilometer.transformer import conversions


class AggregatorTransformerTestCase(base.BaseTestCase):
    SAMPLE = sample.Sample(
        name='cpu',
        type=sample.TYPE_CUMULATIVE,
        unit='ns',
        volume='1234567',
        user_id='56c5692032f34041900342503fecab30',
        project_id='ac9494df2d9d4e709bac378cceabaf23',
        resource_id='1ca738a1-c49c-4401-8346-5c60ebdb03f4',
        timestamp="2015-10-29 14:12:15.485877+00:00",
        resource_metadata={}
    )

    def setUp(self):
        super(AggregatorTransformerTestCase, self).setUp()
        self._sample_offset = 0

    def test_init_input_validation(self):
        aggregator = conversions.AggregatorTransformer("2", "15", None,
                                                       None, None)
        self.assertEqual(2, aggregator.size)
        self.assertEqual(15, aggregator.retention_time)

    def test_init_no_size_or_rention_time(self):
        aggregator = conversions.AggregatorTransformer()
        self.assertEqual(1, aggregator.size)
        self.assertIsNone(aggregator.retention_time)

    def test_init_size_zero(self):
        aggregator = conversions.AggregatorTransformer(size="0")
        self.assertEqual(1, aggregator.size)
        self.assertIsNone(aggregator.retention_time)

    def test_init_input_validation_size_invalid(self):
        self.assertRaises(ValueError, conversions.AggregatorTransformer,
                          "abc", "15", None, None, None)

    def test_init_input_validation_retention_time_invalid(self):
        self.assertRaises(ValueError, conversions.AggregatorTransformer,
                          "2", "abc", None, None, None)

    def test_init_no_timestamp(self):
        aggregator = conversions.AggregatorTransformer("1", "1", None,
                                                       None, None)
        self.assertEqual("first", aggregator.timestamp)

    def test_init_timestamp_none(self):
        aggregator = conversions.AggregatorTransformer("1", "1", None,
                                                       None, None, None)
        self.assertEqual("first", aggregator.timestamp)

    def test_init_timestamp_first(self):
        aggregator = conversions.AggregatorTransformer("1", "1", None,
                                                       None, None, "first")
        self.assertEqual("first", aggregator.timestamp)

    def test_init_timestamp_last(self):
        aggregator = conversions.AggregatorTransformer("1", "1", None,
                                                       None, None, "last")
        self.assertEqual("last", aggregator.timestamp)

    def test_init_timestamp_invalid(self):
        aggregator = conversions.AggregatorTransformer("1", "1", None,
                                                       None, None,
                                                       "invalid_option")
        self.assertEqual("first", aggregator.timestamp)

    def test_size_unbounded(self):
        aggregator = conversions.AggregatorTransformer(size="0",
                                                       retention_time="300")
        self._insert_sample_data(aggregator)

        samples = aggregator.flush()

        self.assertEqual([], samples)

    def test_size_bounded(self):
        aggregator = conversions.AggregatorTransformer(size="100")
        self._insert_sample_data(aggregator)

        samples = aggregator.flush()

        self.assertEqual(100, len(samples))

    def _insert_sample_data(self, aggregator):
        for _ in range(100):
            sample = copy.copy(self.SAMPLE)
            sample.resource_id = sample.resource_id + str(self._sample_offset)
            sample.timestamp = datetime.datetime.isoformat(timeutils.utcnow())
            aggregator.handle_sample(sample)
            self._sample_offset += 1
