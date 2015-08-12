#
# Copyright 2014 Intel Crop.
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
from sqlalchemy import MetaData, Table

TABLES = ['user', 'project', 'alarm']

INDEXES = {
    "alarm": (('user_id', 'user', 'id'),
              ('project_id', 'project', 'id')),
}


def upgrade(migrate_engine):
    if migrate_engine.name == 'sqlite':
        return
    meta = MetaData(bind=migrate_engine)
    load_tables = dict((table_name, Table(table_name, meta, autoload=True))
                       for table_name in TABLES)
    for table_name, indexes in INDEXES.items():
        table = load_tables[table_name]
        for column, ref_table_name, ref_column_name in indexes:
            ref_table = load_tables[ref_table_name]
            params = {'columns': [table.c[column]],
                      'refcolumns': [ref_table.c[ref_column_name]]}
            if migrate_engine.name == 'mysql':
                params['name'] = "_".join(('fk', table_name, column))
            fkey = ForeignKeyConstraint(**params)
            fkey.drop()
