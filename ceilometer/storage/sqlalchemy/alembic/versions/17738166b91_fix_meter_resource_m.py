# -*- encoding: utf-8 -*-
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
"""fix_meter_resource_metadata_type

Revision ID: 17738166b91
Revises: 43b1a023dfaa
Create Date: 2013-08-08 11:20:56.514012

"""

# revision identifiers, used by Alembic.
revision = '17738166b91'
down_revision = '43b1a023dfaa'

from alembic import op
import sqlalchemy as sa


def change_type(type):
    column_old = 'resource_metadata'
    column_new = column_old + '_new'
    bind = op.get_bind()
    meta = sa.MetaData(bind.engine)
    meter = sa.Table('meter', meta, autoload=True)
    new_column = sa.Column(column_new, type)
    new_column.create(meter)
    meter.update().values(resource_metadata_new=meter.c[column_old]).execute()
    meter.c[column_old].drop()
    meter.c[column_new].alter(name=column_old)


def upgrade():
    change_type(sa.Text)


def downgrade():
    change_type(sa.String(5000))
