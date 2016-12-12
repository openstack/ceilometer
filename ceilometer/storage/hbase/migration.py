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
"""HBase storage backend migrations
"""

from ceilometer.storage.hbase import utils as hbase_utils


def migrate_resource_table(conn, table):
    """Migrate table 'resource' in HBase.

    Change qualifiers format from "%s+%s+%s!%s!%s" %
    (rts, source, counter_name, counter_type,counter_unit)
    in columns with meters f:m_*
    to new separator format "%s:%s:%s:%s:%s" %
    (rts, source, counter_name, counter_type,counter_unit)
    """
    resource_table = conn.table(table)
    resource_filter = ("QualifierFilter(=, "
                       "'regexstring:m_\\d{19}\\+"
                       "[\\w-\\._]*\\+[\\w-\\._!]')")
    gen = resource_table.scan(filter=resource_filter)
    for row, data in gen:
        columns = []
        updated_columns = dict()
        column_prefix = "f:"
        for column, value in data.items():
            if column.startswith('f:m_'):
                columns.append(column)
                parts = column[2:].split("+", 2)
                parts.extend(parts.pop(2).split("!"))
                column = hbase_utils.prepare_key(*parts)
                updated_columns[column_prefix + column] = value
        resource_table.put(row, updated_columns)
        resource_table.delete(row, columns)


def migrate_meter_table(conn, table):
    """Migrate table 'meter' in HBase.

    Change row format from "%s_%d_%s" % (counter_name, rts, message_signature)
    to new separator format "%s:%s:%s" % (counter_name, rts, message_signature)
    """
    meter_table = conn.table(table)
    meter_filter = ("RowFilter(=, "
                    "'regexstring:[\\w\\._-]*_\\d{19}_\\w*')")
    gen = meter_table.scan(filter=meter_filter)
    for row, data in gen:
        parts = row.rsplit('_', 2)
        new_row = hbase_utils.prepare_key(*parts)
        meter_table.put(new_row, data)
        meter_table.delete(row)


TABLE_MIGRATION_FUNCS = {'resource': migrate_resource_table,
                         'meter': migrate_meter_table}


def migrate_tables(conn, tables):
    if type(tables) is not list:
        tables = [tables]
    for table in tables:
        if table in TABLE_MIGRATION_FUNCS:
            TABLE_MIGRATION_FUNCS.get(table)(conn, table)
