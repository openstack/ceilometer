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


INDEXES = (
    # ([dialects], table_name, index_name, create/delete, uniq/not uniq)
    (['mysql', 'sqlite', 'postgresql'],
     'resource',
     'resource_user_id_project_id_key',
    ('user_id', 'project_id'), True, False),
    (['mysql'], 'source', 'id', ('id',), False, True))


def index_cleanup(engine_names, table_name, uniq_name, columns, create=True,
                  unique=False):
    engine = op.get_bind().engine
    if engine.name not in engine_names:
        return
    if create:
        # We have unique constraint in postgres for `resource` table.
        # But it should be a simple index. So, we should delete unique key
        # before index creation.
        if engine.name == 'postgresql':
            op.drop_constraint(uniq_name, table_name, type_='unique')
        op.create_index(uniq_name, table_name, columns, unique=unique)
    else:
        if unique:
            op.drop_constraint(uniq_name, table_name, type_='unique')
        else:
            op.drop_index(uniq_name, table_name=table_name)
        if engine.name == 'postgresql':
            op.create_unique_constraint(uniq_name, table_name, columns)


def upgrade():
    for engine_names, table_name, uniq_name, columns, create, uniq in INDEXES:
        index_cleanup(engine_names,
                      table_name,
                      uniq_name,
                      columns,
                      create,
                      uniq)


def downgrade():
    for engine_names, table_name, uniq_name, columns, create, uniq in INDEXES:
        index_cleanup(engine_names,
                      table_name,
                      uniq_name,
                      columns,
                      not create,
                      uniq)
