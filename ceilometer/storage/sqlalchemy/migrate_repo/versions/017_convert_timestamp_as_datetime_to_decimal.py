#
# Copyright 2013 Rackspace Hosting
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

import sqlalchemy as sa

from ceilometer.storage.sqlalchemy import migration
from ceilometer.storage.sqlalchemy import models

_col = 'timestamp'


def _convert_data_type(table, col, from_t, to_t, pk_attr='id', index=False):
    temp_col_n = 'convert_data_type_temp_col'
    # Override column we're going to convert with from_t, since the type we're
    # replacing could be custom and we need to tell SQLALchemy how to perform
    # CRUD operations with it.
    table = sa.Table(table.name, table.metadata, sa.Column(col, from_t),
                     extend_existing=True)
    sa.Column(temp_col_n, to_t).create(table)

    key_attr = getattr(table.c, pk_attr)
    orig_col = getattr(table.c, col)
    new_col = getattr(table.c, temp_col_n)

    query = sa.select([key_attr, orig_col])
    for key, value in migration.paged(query):
        (table.update().where(key_attr == key).values({temp_col_n: value}).
         execute())

    orig_col.drop()
    new_col.alter(name=col)
    if index:
        sa.Index('ix_%s_%s' % (table.name, col), new_col).create()


def upgrade(migrate_engine):
    if migrate_engine.name == 'mysql':
        meta = sa.MetaData(bind=migrate_engine)
        meter = sa.Table('meter', meta, autoload=True)
        _convert_data_type(meter, _col, sa.DateTime(),
                           models.PreciseTimestamp(),
                           pk_attr='id', index=True)
