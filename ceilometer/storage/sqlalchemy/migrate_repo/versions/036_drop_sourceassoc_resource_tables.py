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
import sqlalchemy as sa

from ceilometer.storage.sqlalchemy import migration


TABLES = ['sample', 'resource', 'source', 'sourceassoc']
DROP_TABLES = ['resource', 'source', 'sourceassoc']

INDEXES = {
    "sample": (('resource_id', 'resource', 'id'),),
    "sourceassoc": (('sample_id', 'sample', 'id'),
                    ('resource_id', 'resource', 'id'),
                    ('source_id', 'source', 'id'))
}


def upgrade(migrate_engine):
    meta = sa.MetaData(bind=migrate_engine)
    load_tables = dict((table_name, sa.Table(table_name, meta,
                                             autoload=True))
                       for table_name in TABLES)

    # drop foreign keys
    if migrate_engine.name != 'sqlite':
        for table_name, indexes in INDEXES.items():
            table = load_tables[table_name]
            for column, ref_table_name, ref_column_name in indexes:
                ref_table = load_tables[ref_table_name]
                params = {'columns': [table.c[column]],
                          'refcolumns': [ref_table.c[ref_column_name]]}
                fk_table_name = table_name
                if migrate_engine.name == "mysql":
                    params['name'] = "_".join(('fk', fk_table_name, column))
                elif (migrate_engine.name == "postgresql" and
                      table_name == 'sample'):
                    # fk was not renamed in script 030
                    params['name'] = "_".join(('meter', column, 'fkey'))
                fkey = ForeignKeyConstraint(**params)
                fkey.drop()

    # create source field in sample
    sample = load_tables['sample']
    sample.create_column(sa.Column('source_id', sa.String(255)))

    # move source values to samples
    sourceassoc = load_tables['sourceassoc']
    query = (sa.select([sourceassoc.c.sample_id, sourceassoc.c.source_id]).
             where(sourceassoc.c.sample_id.isnot(None)))
    for sample_id, source_id in migration.paged(query):
        (sample.update().where(sample_id == sample.c.id).
         values({'source_id': source_id}).execute())

    # drop tables
    for table_name in DROP_TABLES:
        sa.Table(table_name, meta, autoload=True).drop()
