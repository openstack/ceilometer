# -*- encoding: utf-8 -*-
#
# Copyright 2010-2011 OpenStack Foundation
# Copyright 2012-2013 IBM Corp. #
#
# Authors: Svetlana Shturm <sshturm@mirantis.com>
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
"""Remove extra indexes

Revision ID: b6ae66d05e3
Revises: 17738166b91
Create Date: 2013-08-19 15:54:43.529222

"""

# revision identifiers, used by Alembic.
revision = 'b6ae66d05e3'
down_revision = '17738166b91'

from alembic import op
import sqlalchemy as sa


INDEXES = (
    # ([dialects], table_name, index_name, create/delete, uniq/not_uniq,
    # length_limited)
    (['mysql', 'sqlite', 'postgresql'],
     'resource',
     'resource_user_id_project_id_key',
     ('user_id', 'project_id'), True, False, True),
    (['mysql'], 'source', 'id', ('id',), False, True, False))


def index_cleanup(engine_names, table_name, uniq_name, columns, create,
                  unique, limited):
    bind = op.get_bind()
    engine = bind.engine
    if engine.name not in engine_names:
        return
    if create:
        if limited and engine.name == 'mysql':
            # For some versions of mysql we can get an error
            # "Specified key was too long; max key length is 1000 bytes".
            # We should create an index by hand in this case with limited
            # length of columns.
            meta = sa.MetaData()
            meta.bind = engine
            table = sa.Table(table_name, meta, autoload=True)
            columns_mysql = ",".join((c + "(100)" for c in columns))
            sql = ("create index %s ON %s (%s)" % (uniq_name, table,
                                                   columns_mysql))
            engine.execute(sql)
        else:
            op.create_index(uniq_name, table_name, columns, unique=unique)
    else:
        if unique:
            op.drop_constraint(uniq_name, table_name, type='unique')
        else:
            op.drop_index(uniq_name, table_name=table_name)


def upgrade():
    for (engine_names, table_name, uniq_name, columns, create, uniq,
         limited) in INDEXES:
        index_cleanup(engine_names,
                      table_name,
                      uniq_name,
                      columns,
                      create,
                      uniq,
                      limited)


def downgrade():
    for (engine_names, table_name, uniq_name, columns, create, uniq,
         limited) in INDEXES:
        index_cleanup(engine_names,
                      table_name,
                      uniq_name,
                      columns,
                      not create,
                      uniq,
                      limited)
