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


def downgrade(migrate_engine):
    meta = sa.MetaData(bind=migrate_engine)
    sample = sa.Table('sample', meta, autoload=True)
    resource = sa.Table(
        'resource', meta,
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('resource_metadata', sa.Text),
        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255)),
        sa.Index('ix_resource_project_id', 'project_id'),
        sa.Index('ix_resource_user_id', 'user_id'),
        sa.Index('resource_user_id_project_id_key', 'user_id', 'project_id'),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )
    resource.create()

    source = sa.Table(
        'source', meta,
        sa.Column('id', sa.String(255), primary_key=True),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )
    source.create()

    sourceassoc = sa.Table(
        'sourceassoc', meta,
        sa.Column('sample_id', sa.Integer),
        sa.Column('resource_id', sa.String(255)),
        sa.Column('source_id', sa.String(255)),
        sa.Index('idx_sr', 'source_id', 'resource_id'),
        sa.Index('idx_ss', 'source_id', 'sample_id'),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )
    sourceassoc.create()

    params = {}
    if migrate_engine.name == "mysql":
        params = {'name': 'uniq_sourceassoc0sample_id'}
    uc = UniqueConstraint('sample_id', table=sourceassoc, **params)
    uc.create()

    # reload source/resource tables.
    # NOTE(gordc): fine to skip non-id attributes in table since
    # they're constantly updated and not used by api
    for table, col in [(source, 'source_id'), (resource, 'resource_id')]:
        q = sa.select([sample.c[col]]).distinct()
        # NOTE(sileht): workaround for
        # https://bitbucket.org/zzzeek/sqlalchemy/
        # issue/3044/insert-from-select-union_all
        q.select = lambda: q
        sql_ins = table.insert().from_select([table.c.id], q)
        try:
            migrate_engine.execute(sql_ins)
        except TypeError:
            # from select is empty
            pass

    # reload sourceassoc tables
    for ref_col, col in [('id', 'sample_id'), ('resource_id', 'resource_id')]:
        q = sa.select([sample.c.source_id, sample.c[ref_col]]).distinct()
        q.select = lambda: q
        sql_ins = sourceassoc.insert().from_select([sourceassoc.c.source_id,
                                                    sourceassoc.c[col]], q)
        try:
            migrate_engine.execute(sql_ins)
        except TypeError:
            # from select is empty
            pass

    sample.c.source_id.drop()

    load_tables = dict((table_name, sa.Table(table_name, meta,
                                             autoload=True))
                       for table_name in TABLES)

    # add foreign keys
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
                fkey.create()
