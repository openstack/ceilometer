# -*- encoding: utf-8 -*-
#
# Author: John Tran <jhtran@att.com>
#         Julien Danjou <julien@danjou.info>
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
"""Tests for ceilometer/storage/impl_sqlalchemy.py

.. note::
  In order to run the tests against real SQL server set the environment
  variable CEILOMETER_TEST_SQL_URL to point to a SQL server before running
  the tests.

"""

from oslo.config import cfg

from tests.storage import base
from ceilometer.storage.sqlalchemy.models import table_args


class SQLAlchemyEngineTestBase(base.DBTestBase):
    database_connection = 'sqlite://'


class UserTest(base.UserTest, SQLAlchemyEngineTestBase):
    pass


class ProjectTest(base.ProjectTest, SQLAlchemyEngineTestBase):
    pass


class ResourceTest(base.ResourceTest, SQLAlchemyEngineTestBase):
    pass


class MeterTest(base.MeterTest, SQLAlchemyEngineTestBase):
    pass


class RawSampleTest(base.RawSampleTest, SQLAlchemyEngineTestBase):
    pass


class StatisticsTest(base.StatisticsTest, SQLAlchemyEngineTestBase):
    pass


class CounterDataTypeTest(base.CounterDataTypeTest, SQLAlchemyEngineTestBase):
    pass


def test_model_table_args():
    cfg.CONF.database_connection = 'mysql://localhost'
    assert table_args()
