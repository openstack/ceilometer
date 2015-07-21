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

import datetime

from oslo_utils import timeutils
from oslotest import base

from ceilometer.network import statistics
from ceilometer.network.statistics import driver
from ceilometer import sample


class TestBase(base.BaseTestCase):

    @staticmethod
    def test_subclass_ok():

        class OkSubclass(statistics._Base):

            meter_name = 'foo'
            meter_type = sample.TYPE_GAUGE
            meter_unit = 'B'

        OkSubclass()

    def test_subclass_ng(self):

        class NgSubclass1(statistics._Base):
            """meter_name is lost."""

            meter_type = sample.TYPE_GAUGE
            meter_unit = 'B'

        class NgSubclass2(statistics._Base):
            """meter_type is lost."""

            meter_name = 'foo'
            meter_unit = 'B'

        class NgSubclass3(statistics._Base):
            """meter_unit is lost."""

            meter_name = 'foo'
            meter_type = sample.TYPE_GAUGE

        self.assertRaises(TypeError, NgSubclass1)
        self.assertRaises(TypeError, NgSubclass2)
        self.assertRaises(TypeError, NgSubclass3)


class TestBaseGetSamples(base.BaseTestCase):

    def setUp(self):
        super(TestBaseGetSamples, self).setUp()

        class FakePollster(statistics._Base):
            meter_name = 'foo'
            meter_type = sample.TYPE_CUMULATIVE
            meter_unit = 'bar'

        self.pollster = FakePollster()

    def tearDown(self):
        statistics._Base.drivers = {}
        super(TestBaseGetSamples, self).tearDown()

    @staticmethod
    def _setup_ext_mgr(**drivers):
        statistics._Base.drivers = drivers

    def _make_fake_driver(self, *return_values):
        class FakeDriver(driver.Driver):

            def __init__(self):
                self.index = 0

            def get_sample_data(self, meter_name, parse_url, params, cache):
                if self.index >= len(return_values):
                    yield None
                retval = return_values[self.index]
                self.index += 1
                yield retval
        return FakeDriver

    @staticmethod
    def _make_timestamps(count):
        now = timeutils.utcnow()
        return [(now + datetime.timedelta(seconds=i)).isoformat()
                for i in range(count)]

    def _get_samples(self, *resources):

        return [v for v in self.pollster.get_samples(self, {}, resources)]

    def _assert_sample(self, s, volume, resource_id, resource_metadata,
                       timestamp):
            self.assertEqual('foo', s.name)
            self.assertEqual(sample.TYPE_CUMULATIVE, s.type)
            self.assertEqual('bar', s.unit)
            self.assertEqual(volume, s.volume)
            self.assertIsNone(s.user_id)
            self.assertIsNone(s.project_id)
            self.assertEqual(resource_id, s.resource_id)
            self.assertEqual(timestamp, s.timestamp)
            self.assertEqual(resource_metadata, s.resource_metadata)

    def test_get_samples_one_driver_one_resource(self):
        times = self._make_timestamps(2)
        fake_driver = self._make_fake_driver((1, 'a', {'spam': 'egg'},
                                              times[0]),
                                             (2, 'b', None, times[1]))

        self._setup_ext_mgr(http=fake_driver())

        samples = self._get_samples('http://foo')

        self.assertEqual(1, len(samples))
        self._assert_sample(samples[0], 1, 'a', {'spam': 'egg'}, times[0])

    def test_get_samples_one_driver_two_resource(self):
        times = self._make_timestamps(3)
        fake_driver = self._make_fake_driver((1, 'a', {'spam': 'egg'},
                                              times[0]),
                                             (2, 'b', None, times[1]),
                                             (3, 'c', None, times[2]))

        self._setup_ext_mgr(http=fake_driver())

        samples = self._get_samples('http://foo', 'http://bar')

        self.assertEqual(2, len(samples))
        self._assert_sample(samples[0], 1, 'a', {'spam': 'egg'}, times[0])
        self._assert_sample(samples[1], 2, 'b', None, times[1])

    def test_get_samples_two_driver_one_resource(self):
        times = self._make_timestamps(4)
        fake_driver1 = self._make_fake_driver((1, 'a', {'spam': 'egg'},
                                               times[0]),
                                              (2, 'b', None), times[1])

        fake_driver2 = self._make_fake_driver((11, 'A', None, times[2]),
                                              (12, 'B', None, times[3]))

        self._setup_ext_mgr(http=fake_driver1(), https=fake_driver2())

        samples = self._get_samples('http://foo')

        self.assertEqual(1, len(samples))
        self._assert_sample(samples[0], 1, 'a', {'spam': 'egg'}, times[0])

    def test_get_samples_multi_samples(self):
        times = self._make_timestamps(2)
        fake_driver = self._make_fake_driver([(1, 'a', {'spam': 'egg'},
                                               times[0]),
                                              (2, 'b', None, times[1])])

        self._setup_ext_mgr(http=fake_driver())

        samples = self._get_samples('http://foo')

        self.assertEqual(2, len(samples))
        self._assert_sample(samples[0], 1, 'a', {'spam': 'egg'}, times[0])
        self._assert_sample(samples[1], 2, 'b', None, times[1])

    def test_get_samples_return_none(self):
        fake_driver = self._make_fake_driver(None)

        self._setup_ext_mgr(http=fake_driver())

        samples = self._get_samples('http://foo')

        self.assertEqual(0, len(samples))

    def test_get_samples_return_no_generator(self):
        class NoneFakeDriver(driver.Driver):

            def get_sample_data(self, meter_name, parse_url, params, cache):
                return None

        self._setup_ext_mgr(http=NoneFakeDriver())
        samples = self._get_samples('http://foo')
        self.assertFalse(samples)
