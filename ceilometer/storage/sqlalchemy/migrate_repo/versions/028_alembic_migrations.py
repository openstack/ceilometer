#
# Copyright 2014 OpenStack Foundation
# All Rights Reserved.
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
import migrate
import sqlalchemy as sa


def get_alembic_version(meta):
    """Return Alembic version or None if no Alembic table exists."""
    try:
        a_ver = sa.Table(
            'alembic_version',
            meta,
            autoload=True)
        return sa.select([a_ver.c.version_num]).scalar()
    except sa.exc.NoSuchTableError:
        return None


def delete_alembic(meta):
    try:
        sa.Table(
            'alembic_version',
            meta,
            autoload=True).drop(checkfirst=True)
    except sa.exc.NoSuchTableError:
        pass


INDEXES = (
    # ([dialects], table_name, index_name, create/delete, uniq/not_uniq)
    (['mysql', 'sqlite', 'postgresql'],
     'resource',
     'resource_user_id_project_id_key',
     ('user_id', 'project_id'), True, False, True),
    (['mysql'], 'source', 'id', ('id',), False, True, False))


def index_cleanup(meta, table_name, uniq_name, columns,
                  create, unique, limited):
    table = sa.Table(table_name, meta, autoload=True)
    if create:
        if limited and meta.bind.engine.name == 'mysql':
            # For some versions of mysql we can get an error
            # "Specified key was too long; max key length is 1000 bytes".
            # We should create an index by hand in this case with limited
            # length of columns.
            columns_mysql = ",".join((c + "(100)" for c in columns))
            sql = ("create index %s ON %s (%s)" % (uniq_name, table,
                                                   columns_mysql))
            meta.bind.engine.execute(sql)
        else:
            cols = [table.c[col] for col in columns]
            sa.Index(uniq_name, *cols, unique=unique).create()
    else:
        if unique:
            migrate.UniqueConstraint(*columns, table=table,
                                     name=uniq_name).drop()
        else:
            cols = [table.c[col] for col in columns]
            sa.Index(uniq_name, *cols).drop()


def change_uniq(meta):
    uniq_name = 'uniq_sourceassoc0meter_id0user_id'
    columns = ('meter_id', 'user_id')

    if meta.bind.engine.name == 'sqlite':
        return

    sourceassoc = sa.Table('sourceassoc', meta, autoload=True)
    meter = sa.Table('meter', meta, autoload=True)
    user = sa.Table('user', meta, autoload=True)
    if meta.bind.engine.name == 'mysql':
        # For mysql dialect all dependent FK should be removed
        #  before renaming of constraint.
        params = {'columns': [sourceassoc.c.meter_id],
                  'refcolumns': [meter.c.id],
                  'name': 'fk_sourceassoc_meter_id'}
        migrate.ForeignKeyConstraint(**params).drop()
        params = {'columns': [sourceassoc.c.user_id],
                  'refcolumns': [user.c.id],
                  'name': 'fk_sourceassoc_user_id'}
        migrate.ForeignKeyConstraint(**params).drop()

    migrate.UniqueConstraint(*columns, table=sourceassoc,
                             name=uniq_name).create()
    if meta.bind.engine.name == 'mysql':
        params = {'columns': [sourceassoc.c.meter_id],
                  'refcolumns': [meter.c.id],
                  'name': 'fk_sourceassoc_meter_id'}
        migrate.ForeignKeyConstraint(**params).create()
        params = {'columns': [sourceassoc.c.user_id],
                  'refcolumns': [user.c.id],
                  'name': 'fk_sourceassoc_user_id'}
        migrate.ForeignKeyConstraint(**params).create()


def upgrade(migrate_engine):
    meta = sa.MetaData(bind=migrate_engine)
    a_ver = get_alembic_version(meta)

    if not a_ver:
        alarm = sa.Table('alarm', meta, autoload=True)
        repeat_act = sa.Column('repeat_actions', sa.Boolean,
                               server_default=sa.sql.expression.false())
        alarm.create_column(repeat_act)
        a_ver = '43b1a023dfaa'

    if a_ver == '43b1a023dfaa':
        meter = sa.Table('meter', meta, autoload=True)
        meter.c.resource_metadata.alter(type=sa.Text)
        a_ver = '17738166b91'

    if a_ver == '17738166b91':
        for (engine_names, table_name, uniq_name,
             columns, create, uniq, limited) in INDEXES:
            if migrate_engine.name in engine_names:
                index_cleanup(meta, table_name, uniq_name,
                              columns, create, uniq, limited)
        a_ver = 'b6ae66d05e3'

    if a_ver == 'b6ae66d05e3':
        change_uniq(meta)

    delete_alembic(meta)
