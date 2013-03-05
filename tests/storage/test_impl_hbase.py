# -*- encoding: utf-8 -*-
#
# Copyright © 2012, 2013 Dell Inc.
#
# Author: Stas Maksimov <Stanislav_M@dell.com>
# Author: Shengjie Min <Shengjie_Min@dell.com>
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
"""Tests for ceilometer/storage/impl_hbase.py

.. note::
  To run the tests using in-memory mocked HappyBase API,
  set the environment variable CEILOMETER_TEST_LIVE=0 (this is the default
  value)

  In order to run the tests against real HBase server set the environment
  variable CEILOMETER_TEST_LIVE=1 and set HBASE_URL below to
  point to that HBase instance before running the tests. Make sure the Thrift
  server is running on that server.

"""

from time import sleep
import logging

import os
import copy
import re

from oslo.config import cfg

from tests.storage import base
from ceilometer.storage import impl_hbase

from ceilometer.storage.impl_hbase import _load_hbase_list

LOG = logging.getLogger(__name__)

CEILOMETER_TEST_LIVE = bool(int(os.environ.get('CEILOMETER_TEST_LIVE', 0)))

# Export this variable before running tests against real HBase
# e.g. export CEILOMETER_TEST_HBASE_URL = hbase://192.168.1.100:9090
CEILOMETER_TEST_HBASE_URL = os.environ.get('CEILOMETER_TEST_HBASE_URL')
if CEILOMETER_TEST_LIVE:
    if not CEILOMETER_TEST_HBASE_URL:
        raise RuntimeError("CEILOMETER_TEST_LIVE is on, but "
                           "CEILOMETER_TEST_HBASE_URL is not defined")
PROJECT_TABLE = "project"
USER_TABLE = "user"
RESOURCE_TABLE = "resource"
METER_TABLE = "meter"

TABLES = [PROJECT_TABLE, USER_TABLE, RESOURCE_TABLE, METER_TABLE]


class TestConnection(impl_hbase.Connection):

    def __init__(self, conf):
        if CEILOMETER_TEST_LIVE:
            super(TestConnection, self).__init__(conf)
        else:
            self.conn = MConnection()
            self.project = self.conn.table('project')
            self.user = self.conn.table('user')
            self.resource = self.conn.table('resource')
            self.meter = self.conn.table('meter')

    def create_schema(self):
        LOG.debug('Creating HBase schema...')
        self.conn.create_table(PROJECT_TABLE, {'f': dict()})
        self.conn.create_table(USER_TABLE, {'f': dict()})
        self.conn.create_table(RESOURCE_TABLE, {'f': dict()})
        self.conn.create_table(METER_TABLE, {'f': dict()})
        # Real HBase needs some time to propagate create_table changes
        if CEILOMETER_TEST_LIVE:
            sleep(10)

    def drop_schema(self):
        LOG.debug('Dropping HBase schema...')
        for table in TABLES:
            try:
                self.conn.disable_table(table)
            except:
                None
            try:
                self.conn.delete_table(table)
            except:
                None
            # Real HBase needs some time to propagate delete_table changes
            if CEILOMETER_TEST_LIVE:
                sleep(10)


class HBaseEngine(base.DBEngineBase):

    def get_connection(self):
        self.conf = cfg.CONF

        self.conf.database_connection = CEILOMETER_TEST_HBASE_URL
        # use prefix so we don't affect any existing tables
        self.conf.table_prefix = 't'

        self.conn = TestConnection(self.conf)

        self.conn.drop_schema()
        self.conn.create_schema()

        self.conn.upgrade()
        return self.conn

    def clean_up(self):
        pass

    def get_sources_by_project_id(self, id):
        project = self.conn.project.row(id)
        return _load_hbase_list(project, 's')

    def get_sources_by_user_id(self, id):
        user = self.conn.user.row(id)
        return _load_hbase_list(user, 's')


class HBaseEngineTestBase(base.DBTestBase):

    def get_engine(cls):
        return HBaseEngine()


class UserTest(base.UserTest, HBaseEngineTestBase):
    pass


class ProjectTest(base.ProjectTest, HBaseEngineTestBase):
    pass


class ResourceTest(base.ResourceTest, HBaseEngineTestBase):
    pass


class MeterTest(base.MeterTest, HBaseEngineTestBase):
    pass


class RawEventTest(base.RawEventTest, HBaseEngineTestBase):
    pass


class TestGetEventInterval(base.TestGetEventInterval,
                           HBaseEngineTestBase):
    pass


class SumTest(base.SumTest, HBaseEngineTestBase):
    pass


class MaxProjectTest(base.MaxProjectTest, HBaseEngineTestBase):
    pass


class MaxResourceTest(base.MaxResourceTest, HBaseEngineTestBase):
    pass


class StatisticsTest(base.StatisticsTest, HBaseEngineTestBase):
    pass


###############
# This is a very crude version of "in-memory HBase", which implements just
# enough functionality of HappyBase API to support testing of our driver.
#
class MTable():
    """HappyBase.Table mock
    """
    def __init__(self, name, families):
        self.name = name
        self.families = families
        self.rows = {}

    def row(self, key):
        return self.rows[key] if key in self.rows else {}

    def put(self, key, data):
        self.rows[key] = data

    def scan(self, filter=None, columns=[], row_start=None, row_stop=None):
        sorted_keys = sorted(self.rows)
        # copy data into a sorted dict
        rows = {}
        for row in sorted_keys:
            if row_start:
                if row < row_start:
                    continue
            if row_stop:
                if row > row_stop:
                    break
            rows[row] = copy.copy(self.rows[row])
        if columns:
            ret = {}
            for row in rows.keys():
                data = rows[row]
                for key in data:
                #    if all(key in columns for key in data):
                    if key in columns:
                        ret[row] = data
            rows = ret
        elif filter:
            # TODO: we should really parse this properly, but at the moment we
            # are only going to support AND here
            filters = filter.split('AND')
            for f in filters:
                # Extract filter name and its arguments
                g = re.search("(.*)\((.*),?\)", f)
                fname = g.group(1).strip()
                fargs = [s.strip().replace('\'', '').replace('\"', '')
                         for s in g.group(2).split(',')]
                m = getattr(self, fname)
                if callable(m):
                    # overwrite rows for filtering to take effect
                    # in case of multiple filters
                    rows = m(fargs, rows)
                else:
                    raise NotImplementedError("%s filter is not implemented, "
                                              "you may want to add it!")
        for k in sorted(rows):
            yield k, rows[k]

    def SingleColumnValueFilter(self, args, rows):
        """This method is called from scan() when 'SingleColumnValueFilter'
        is found in the 'filter' argument
        """
        op = args[2]
        column = "%s:%s" % (args[0], args[1])
        value = args[3]
        if value.startswith('binary:'):
            value = value[7:]
        r = {}
        for row in rows:
            data = rows[row]

            if op == '=':
                if column in data and data[column] == value:
                    r[row] = data
            elif op == '<=':
                if column in data and data[column] <= value:
                    r[row] = data
            elif op == '>=':
                if column in data and data[column] >= value:
                    r[row] = data
            else:
                raise NotImplementedError("In-memory "
                                          "SingleColumnValueFilter "
                                          "doesn't support the %s operation "
                                          "yet" % op)
        return r


class MConnection():
    """HappyBase.Connection mock
    """
    def __init__(self):
        self.tables = {}

    def open(self):
        LOG.debug("Opening in-memory HBase connection")
        return

    def create_table(self, n, families={}):
        if n in self.tables:
            return self.tables[n]
        t = MTable(n, families)
        self.tables[n] = t
        return t

    def delete_table(self, name, use_prefix=True):
        self.tables.remove(self.tables[name])

    def table(self, name):
        return self.create_table(name)
