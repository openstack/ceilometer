# -*- encoding: utf-8 -*-
#
# Author: John Tran <jhtran@att.com>
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
"""

import logging
import os
import sqlalchemy
import re

from tests.storage import base
from ceilometer.openstack.common import cfg
from ceilometer import storage
from ceilometer.storage import impl_sqlalchemy
from ceilometer.storage.sqlalchemy.models import Meter, Project, Resource, User
from ceilometer.storage.sqlalchemy.models import table_args


LOG = logging.getLogger(__name__)
CEILOMETER_TEST_LIVE = bool(int(os.environ.get('CEILOMETER_TEST_LIVE', 0)))
if CEILOMETER_TEST_LIVE:
    MYSQL_DBNAME = 'ceilometer_test'
    MYSQL_BASE_URL = 'mysql://ceilometer:somepass@localhost/'
    MYSQL_URL = MYSQL_BASE_URL + MYSQL_DBNAME


class Connection(impl_sqlalchemy.Connection):

    def _get_connection(self, conf):
        try:
            return super(Connection, self)._get_connection(conf)
        except:
            LOG.debug('Unable to connect to %s' % conf.database_connection)
            raise


class SQLAlchemyEngine(base.DBEngineBase):

    def clean_up(self):
        engine_conn = self.session.bind.connect()
        if CEILOMETER_TEST_LIVE:
            engine_conn.execute('drop database %s' % MYSQL_DBNAME)
            engine_conn.execute('create database %s' % MYSQL_DBNAME)
        # needed for sqlite in-memory db to destroy
        self.session.close_all()
        self.session.bind.dispose()

    def get_connection(self):
        self.conf = cfg.CONF
        self.conf.database_connection = 'sqlite://'
        # Use a real MySQL server if we can connect, but fall back
        # to a Sqlite in-memory connection if we cannot.
        if CEILOMETER_TEST_LIVE:
            # should pull from conf file but for now manually specified
            # just make sure ceilometer_test db exists in mysql
            self.conf.database_connection = MYSQL_URL
            engine = sqlalchemy.create_engine(MYSQL_BASE_URL)
            engine_conn = engine.connect()
            try:
                engine_conn.execute('drop database %s' % MYSQL_DBNAME)
            except sqlalchemy.exc.OperationalError:
                pass
            engine_conn.execute('create database %s' % MYSQL_DBNAME)

        self.conn = Connection(self.conf)
        self.session = self.conn.session
        self.conn.upgrade()
        return self.conn

    def get_sources_by_project_id(self, id):
        project = self.session.query(Project).get('project-id')
        return map(lambda x: x.id, project.sources)

    def get_sources_by_user_id(self, id):
        user = self.session.query(User).get('user-id')
        return map(lambda x: x.id, user.sources)


class SQLAlchemyEngineTestBase(base.DBTestBase):

    def get_engine(cls):
        return SQLAlchemyEngine()


class UserTest(base.UserTest, SQLAlchemyEngineTestBase):
    pass


class ProjectTest(base.ProjectTest, SQLAlchemyEngineTestBase):
    pass


class ResourceTest(base.ResourceTest, SQLAlchemyEngineTestBase):
    pass


class MeterTest(base.MeterTest, SQLAlchemyEngineTestBase):
    pass


class RawEventTest(base.RawEventTest, SQLAlchemyEngineTestBase):

    def _compare_raw(self, msg_dict, result_dict):
        for k, v in msg_dict.items():
            if k in ['timestamp', 'source']:
                continue
            if k == 'resource_metadata':
                key = result_dict[k]
                value = v
            else:
                key = str(result_dict[k])
                value = str(v)
            assert key == value

    def _iterate_msgs(self, results):
        for meter in results:
            labels = map(lambda x: x['id'], meter['sources'])
            # should only have one source
            assert len(labels) == 1
            count = re.match('test-(\d+)', labels[0]).group(1)
            self._compare_raw(getattr(self, 'msg' + count), meter)

    def test_get_raw_events_by_user(self):
        f = storage.EventFilter(user='user-id')
        results = list(self.conn.get_raw_events(f))
        assert len(results) == 2
        self._iterate_msgs(results)

    def test_get_raw_events_by_project(self):
        f = storage.EventFilter(project='project-id')
        results = list(self.conn.get_raw_events(f))
        assert len(results) == 3
        self._iterate_msgs(results)

    def test_get_raw_events_by_resource(self):
        f = storage.EventFilter(user='user-id', resource='resource-id')
        results = list(self.conn.get_raw_events(f))
        assert len(results) == 1
        self._compare_raw(self.msg1, results[0])


class TestGetEventInterval(base.TestGetEventInterval,
                           SQLAlchemyEngineTestBase):
    pass


class SumTest(base.SumTest, SQLAlchemyEngineTestBase):
    pass


class MaxProjectTest(base.MaxProjectTest, SQLAlchemyEngineTestBase):
    pass


class MaxResourceTest(base.MaxResourceTest, SQLAlchemyEngineTestBase):
    pass


class StatisticsTest(base.StatisticsTest, SQLAlchemyEngineTestBase):
    pass


def test_model_table_args():
    cfg.CONF.database_connection = 'mysql://localhost'
    assert table_args()
