# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
#
# Authors: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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
"""Add column repeat_alarms

Revision ID: 43b1a023dfaa
Revises: None
Create Date: 2013-07-29 17:25:53.931326

"""

# revision identifiers, used by Alembic.
revision = '43b1a023dfaa'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('alarm', sa.Column('repeat_actions',
                                     sa.Boolean,
                                     server_default=sa.sql.expression.false()))


def downgrade():
    op.drop_column('alarm', 'repeat_actions')
