#
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

from sqlalchemy import Index, MetaData, Table


INDEXES = {
    # `table_name`: ((`index_name`, `column`),)
    "user": (('ix_user_id', 'id'),),
    "source": (('ix_source_id', 'id'),),
    "project": (('ix_project_id', 'id'),),
    "meter": (('ix_meter_id', 'id'),),
    "alarm": (('ix_alarm_id', 'id'),),
    "resource": (('ix_resource_id', 'id'),)
}


def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    load_tables = dict((table_name, Table(table_name, meta, autoload=True))
                       for table_name in INDEXES.keys())
    for table_name, indexes in INDEXES.items():
        table = load_tables[table_name]
        for index_name, column in indexes:
            index = Index(index_name, table.c[column])
            index.drop()
