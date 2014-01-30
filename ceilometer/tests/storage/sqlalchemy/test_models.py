# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Rackspace Hosting
#
# Author: Thomas Maddox <thomas.maddox@rackspace.com>
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

import mock
import sqlalchemy
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.types import NUMERIC

from ceilometer.openstack.common import test
from ceilometer.storage.sqlalchemy import models
from ceilometer import utils


class PreciseTimestampTest(test.BaseTestCase):

    @staticmethod
    def fake_dialect(name):
        def _type_descriptor_mock(desc):
            if type(desc) == DECIMAL:
                return NUMERIC(precision=desc.precision, scale=desc.scale)
        dialect = mock.MagicMock()
        dialect.name = name
        dialect.type_descriptor = _type_descriptor_mock
        return dialect

    def setUp(self):
        super(PreciseTimestampTest, self).setUp()
        self._mysql_dialect = self.fake_dialect('mysql')
        self._postgres_dialect = self.fake_dialect('postgres')
        self._type = models.PreciseTimestamp()
        self._date = datetime.datetime(2012, 7, 2, 10, 44)

    def test_load_dialect_impl_mysql(self):
        result = self._type.load_dialect_impl(self._mysql_dialect)
        self.assertEqual(type(result), NUMERIC)
        self.assertEqual(result.precision, 20)
        self.assertEqual(result.scale, 6)
        self.assertTrue(result.asdecimal)

    def test_load_dialect_impl_postgres(self):
        result = self._type.load_dialect_impl(self._postgres_dialect)
        self.assertEqual(type(result), sqlalchemy.DateTime)

    def test_process_bind_param_store_decimal_mysql(self):
        expected = utils.dt_to_decimal(self._date)
        result = self._type.process_bind_param(self._date, self._mysql_dialect)
        self.assertEqual(result, expected)

    def test_process_bind_param_store_datetime_postgres(self):
        result = self._type.process_bind_param(self._date,
                                               self._postgres_dialect)
        self.assertEqual(result, self._date)

    def test_process_bind_param_store_none_mysql(self):
        result = self._type.process_bind_param(None, self._mysql_dialect)
        self.assertIsNone(result)

    def test_process_bind_param_store_none_postgres(self):
        result = self._type.process_bind_param(None,
                                               self._postgres_dialect)
        self.assertIsNone(result)

    def test_process_result_value_datetime_mysql(self):
        dec_value = utils.dt_to_decimal(self._date)
        result = self._type.process_result_value(dec_value,
                                                 self._mysql_dialect)
        self.assertEqual(result, self._date)

    def test_process_result_value_datetime_postgres(self):
        result = self._type.process_result_value(self._date,
                                                 self._postgres_dialect)
        self.assertEqual(result, self._date)

    def test_process_result_value_none_mysql(self):
        result = self._type.process_result_value(None,
                                                 self._mysql_dialect)
        self.assertIsNone(result)

    def test_process_result_value_none_postgres(self):
        result = self._type.process_result_value(None,
                                                 self._postgres_dialect)
        self.assertIsNone(result)
