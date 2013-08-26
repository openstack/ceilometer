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
"""Fix name of UniqueConstraint according to OpenStack naming convention

Revision ID: 2c3ccda5a3ad
Revises: b6ae66d05e3
Create Date: 2013-08-19 18:06:03.409584

"""

# revision identifiers, used by Alembic.
revision = '2c3ccda5a3ad'
down_revision = 'b6ae66d05e3'

from alembic import op


TABLE_NAME = 'sourceassoc'
OLD_NAME = 'uniq_sourceassoc0meter_id'
NEW_NAME = 'uniq_sourceassoc0meter_id0user_id'
COLUMNS = ('meter_id', 'user_id')


def change_uniq(table_name, old_name, new_name, columns):
    engine = op.get_bind().engine
    if engine.name == 'sqlite':
        return
    if engine.name == 'mysql':
        # For mysql dialect all dependent FK should be removed
        #  before renaming of constraint.
        op.drop_constraint('fk_sourceassoc_meter_id',
                           table_name,
                           type_='foreignkey')
        op.drop_constraint('fk_sourceassoc_user_id',
                           table_name,
                           type_='foreignkey')
    try:
        # For some versions of dialects constraint can be skipped.
        op.drop_constraint(old_name, table_name=table_name, type_='unique')
    except Exception:
        pass
    op.create_unique_constraint(new_name, table_name, columns)
    if engine.name == 'mysql':
        op.create_foreign_key('fk_sourceassoc_meter_id', table_name, 'meter',
                              ['meter_id'], ['id'])
        op.create_foreign_key('fk_sourceassoc_user_id', table_name, 'user',
                              ['user_id'], ['id'])


def upgrade():
    change_uniq(TABLE_NAME, OLD_NAME, NEW_NAME, COLUMNS)


def downgrade():
    change_uniq(TABLE_NAME, NEW_NAME, OLD_NAME, COLUMNS)
