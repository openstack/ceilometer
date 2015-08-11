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

TABLES_012 = ['resource', 'sourceassoc', 'user',
              'project', 'meter', 'source', 'alarm']
TABLES_027 = ['user', 'project', 'alarm']


def upgrade(migrate_engine):
    meta = sa.MetaData(bind=migrate_engine)
    for table_name in TABLES_027:
        try:
            (sa.Table('dump027_' + table_name, meta, autoload=True).
             drop(checkfirst=True))
        except sa.exc.NoSuchTableError:
            pass
    for table_name in TABLES_012:
        try:
            (sa.Table('dump_' + table_name, meta, autoload=True).
             drop(checkfirst=True))
        except sa.exc.NoSuchTableError:
            pass
