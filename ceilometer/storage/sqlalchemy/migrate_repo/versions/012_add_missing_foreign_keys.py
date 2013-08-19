# -*- encoding: utf-8 -*-
#
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

from migrate import ForeignKeyConstraint
from sqlalchemy import MetaData, Table
from sqlalchemy.sql.expression import select

from ceilometer.openstack.common.db.sqlalchemy import utils

TABLES = ['resource', 'sourceassoc', 'user',
          'project', 'meter', 'source', 'alarm']

INDEXES = {
    "resource": (('user_id', 'user', 'id'),
                 ('project_id', 'project', 'id')),
    "sourceassoc": (('user_id', 'user', 'id'),
                    ('project_id', 'project', 'id'),
                    ('resource_id', 'resource', 'id'),
                    ('meter_id', 'meter', 'id'),
                    ('source_id', 'source', 'id')),
    "alarm": (('user_id', 'user', 'id'),
              ('project_id', 'project', 'id')),
    "meter": (('user_id', 'user', 'id'),
              ('project_id', 'project', 'id'),
              ('resource_id', 'resource', 'id'),)
}


def upgrade(migrate_engine):
    if migrate_engine.name == 'sqlite':
        return
    meta = MetaData(bind=migrate_engine)
    load_tables = dict((table_name, Table(table_name, meta, autoload=True))
                       for table_name in TABLES)
    for table_name, indexes in INDEXES.items():
        table = load_tables[table_name]

        # Save data that conflicted with FK.
        columns = [column.copy() for column in table.columns]
        table_dump = Table('dump_' + table_name, meta, *columns)
        table_dump.create()
        for column, ref_table_name, ref_column_name in indexes:
            ref_table = load_tables[ref_table_name]
            subq = select([getattr(ref_table.c, ref_column_name)])
            sql = utils.InsertFromSelect(table_dump, table.select().where(
                ~ getattr(table.c, column).in_(subq)))
            sql_del = table.delete().where(
                ~ getattr(table.c, column).in_(subq))
            migrate_engine.execute(sql)
            migrate_engine.execute(sql_del)

            params = {'columns': [table.c[column]],
                      'refcolumns': [ref_table.c[ref_column_name]]}
            if migrate_engine.name == 'mysql':
                params['name'] = "_".join(('fk', table_name, column))
            fkey = ForeignKeyConstraint(**params)
            fkey.create()


def downgrade(migrate_engine):
    if migrate_engine.name == 'sqlite':
        return
    meta = MetaData(bind=migrate_engine)
    load_tables = dict((table_name, Table(table_name, meta, autoload=True))
                       for table_name in TABLES)
    for table_name, indexes in INDEXES.items():
        table = load_tables[table_name]
        for column, ref_table_name, ref_column_name in indexes:
            ref_table = load_tables[ref_table_name]
            params = {'columns': [table.c[column]],
                      'refcolumns': [ref_table.c[ref_column_name]]}
            if migrate_engine.name == 'mysql':
                params['name'] = "_".join(('fk', table_name, column))
            with migrate_engine.begin():
                fkey = ForeignKeyConstraint(**params)
                fkey.drop()
        with migrate_engine.begin():
            # Restore data that had been dropped.
            table_dump_name = 'dump_' + table_name
            table_dump = Table(table_dump_name, meta, autoload=True)
            sql = utils.InsertFromSelect(table, table_dump.select())
            migrate_engine.execute(sql)
            table_dump.drop()
