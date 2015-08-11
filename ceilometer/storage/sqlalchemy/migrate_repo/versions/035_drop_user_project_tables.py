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

from migrate import ForeignKeyConstraint, UniqueConstraint
import sqlalchemy as sa

TABLES_DROP = ['user', 'project']
TABLES = ['user', 'project', 'sourceassoc', 'sample',
          'resource', 'alarm_history']

INDEXES = {
    "sample": (('user_id', 'user', 'id'),
               ('project_id', 'project', 'id')),
    "sourceassoc": (('user_id', 'user', 'id'),
                    ('project_id', 'project', 'id')),
    "resource": (('user_id', 'user', 'id'),
                 ('project_id', 'project', 'id')),
    "alarm_history": (('user_id', 'user', 'id'),
                      ('project_id', 'project', 'id'),
                      ('on_behalf_of', 'project', 'id')),
}


def upgrade(migrate_engine):
    meta = sa.MetaData(bind=migrate_engine)
    load_tables = dict((table_name, sa.Table(table_name, meta,
                                             autoload=True))
                       for table_name in TABLES)

    if migrate_engine.name != 'sqlite':
        for table_name, indexes in INDEXES.items():
            table = load_tables[table_name]
            for column, ref_table_name, ref_column_name in indexes:
                ref_table = load_tables[ref_table_name]
                params = {'columns': [table.c[column]],
                          'refcolumns': [ref_table.c[ref_column_name]]}

                if (migrate_engine.name == "mysql" and
                        table_name != 'alarm_history'):
                    params['name'] = "_".join(('fk', table_name, column))
                elif (migrate_engine.name == "postgresql" and
                        table_name == "sample"):
                    # The fk contains the old table name
                    params['name'] = "_".join(('meter', column, 'fkey'))

                fkey = ForeignKeyConstraint(**params)
                fkey.drop()

    sourceassoc = load_tables['sourceassoc']
    if migrate_engine.name != 'sqlite':
        idx = sa.Index('idx_su', sourceassoc.c.source_id,
                       sourceassoc.c.user_id)
        idx.drop(bind=migrate_engine)
        idx = sa.Index('idx_sp', sourceassoc.c.source_id,
                       sourceassoc.c.project_id)
        idx.drop(bind=migrate_engine)

        params = {}
        if migrate_engine.name == "mysql":
            params = {'name': 'uniq_sourceassoc0sample_id'}
        uc = UniqueConstraint('sample_id', table=sourceassoc, **params)
        uc.create()

        params = {}
        if migrate_engine.name == "mysql":
            params = {'name': 'uniq_sourceassoc0sample_id0user_id'}
        uc = UniqueConstraint('sample_id', 'user_id',
                              table=sourceassoc, **params)
        uc.drop()
    sourceassoc.c.user_id.drop()
    sourceassoc.c.project_id.drop()

    for table_name in TABLES_DROP:
        sa.Table(table_name, meta, autoload=True).drop()
