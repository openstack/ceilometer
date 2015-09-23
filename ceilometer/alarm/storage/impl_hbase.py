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

import datetime
import operator

from oslo_log import log

import ceilometer
from ceilometer.alarm.storage import base
from ceilometer.alarm.storage import models
from ceilometer.storage.hbase import base as hbase_base
from ceilometer.storage.hbase import migration as hbase_migration
from ceilometer.storage.hbase import utils as hbase_utils
from ceilometer import utils

LOG = log.getLogger(__name__)


AVAILABLE_CAPABILITIES = {
    'alarms': {'query': {'simple': True,
                         'complex': False},
               'history': {'query': {'simple': True,
                                     'complex': False}}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


class Connection(hbase_base.Connection, base.Connection):
    """Put the alarm data into a HBase database

    Collections:

    - alarm:

      - row_key: uuid of alarm
      - Column Families:

        f: contains the raw incoming alarm data

    - alarm_h:

      - row_key: uuid of alarm + ":" + reversed timestamp
      - Column Families:

        f: raw incoming alarm_history data. Timestamp becomes now()
          if not determined
    """

    CAPABILITIES = utils.update_nested(base.Connection.CAPABILITIES,
                                       AVAILABLE_CAPABILITIES)
    STORAGE_CAPABILITIES = utils.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )
    _memory_instance = None

    ALARM_TABLE = "alarm"
    ALARM_HISTORY_TABLE = "alarm_h"

    def __init__(self, url):
        super(Connection, self).__init__(url)

    def upgrade(self):
        tables = [self.ALARM_HISTORY_TABLE, self.ALARM_TABLE]
        column_families = {'f': dict()}
        with self.conn_pool.connection() as conn:
            hbase_utils.create_tables(conn, tables, column_families)
            hbase_migration.migrate_tables(conn, tables)

    def clear(self):
        LOG.debug('Dropping HBase schema...')
        with self.conn_pool.connection() as conn:
            for table in [self.ALARM_TABLE,
                          self.ALARM_HISTORY_TABLE]:
                try:
                    conn.disable_table(table)
                except Exception:
                    LOG.debug('Cannot disable table but ignoring error')
                try:
                    conn.delete_table(table)
                except Exception:
                    LOG.debug('Cannot delete table but ignoring error')

    def update_alarm(self, alarm):
        """Create an alarm.

        :param alarm: The alarm to create. It is Alarm object, so we need to
          call as_dict()
        """
        _id = alarm.alarm_id
        alarm_to_store = hbase_utils.serialize_entry(alarm.as_dict())
        with self.conn_pool.connection() as conn:
            alarm_table = conn.table(self.ALARM_TABLE)
            alarm_table.put(_id, alarm_to_store)
            stored_alarm = hbase_utils.deserialize_entry(
                alarm_table.row(_id))[0]
        return models.Alarm(**stored_alarm)

    create_alarm = update_alarm

    def delete_alarm(self, alarm_id):
        """Delete an alarm and its history data."""
        with self.conn_pool.connection() as conn:
            alarm_table = conn.table(self.ALARM_TABLE)
            alarm_table.delete(alarm_id)
            q = hbase_utils.make_query(alarm_id=alarm_id)
            alarm_history_table = conn.table(self.ALARM_HISTORY_TABLE)
            for alarm_id, ignored in alarm_history_table.scan(filter=q):
                alarm_history_table.delete(alarm_id)

    def get_alarms(self, name=None, user=None, state=None, meter=None,
                   project=None, enabled=None, alarm_id=None,
                   alarm_type=None, severity=None):

        if meter:
            raise ceilometer.NotImplementedError(
                'Filter by meter not implemented')

        q = hbase_utils.make_query(alarm_id=alarm_id, name=name,
                                   enabled=enabled, user_id=user,
                                   project_id=project, state=state,
                                   type=alarm_type, severity=severity)

        with self.conn_pool.connection() as conn:
            alarm_table = conn.table(self.ALARM_TABLE)
            gen = alarm_table.scan(filter=q)
            alarms = [hbase_utils.deserialize_entry(data)[0]
                      for ignored, data in gen]
            for alarm in sorted(
                    alarms,
                    key=operator.itemgetter('timestamp'),
                    reverse=True):
                yield models.Alarm(**alarm)

    def get_alarm_changes(self, alarm_id, on_behalf_of,
                          user=None, project=None, alarm_type=None,
                          severity=None, start_timestamp=None,
                          start_timestamp_op=None, end_timestamp=None,
                          end_timestamp_op=None):
        q = hbase_utils.make_query(alarm_id=alarm_id,
                                   on_behalf_of=on_behalf_of, type=alarm_type,
                                   user_id=user, project_id=project,
                                   severity=severity)
        start_row, end_row = hbase_utils.make_timestamp_query(
            hbase_utils.make_general_rowkey_scan,
            start=start_timestamp, start_op=start_timestamp_op,
            end=end_timestamp, end_op=end_timestamp_op, bounds_only=True,
            some_id=alarm_id)
        with self.conn_pool.connection() as conn:
            alarm_history_table = conn.table(self.ALARM_HISTORY_TABLE)
            gen = alarm_history_table.scan(filter=q, row_start=start_row,
                                           row_stop=end_row)
            for ignored, data in gen:
                stored_entry = hbase_utils.deserialize_entry(data)[0]
                yield models.AlarmChange(**stored_entry)

    def record_alarm_change(self, alarm_change):
        """Record alarm change event."""
        alarm_change_dict = hbase_utils.serialize_entry(alarm_change)
        ts = alarm_change.get('timestamp') or datetime.datetime.now()
        rts = hbase_utils.timestamp(ts)
        with self.conn_pool.connection() as conn:
            alarm_history_table = conn.table(self.ALARM_HISTORY_TABLE)
            alarm_history_table.put(
                hbase_utils.prepare_key(alarm_change.get('alarm_id'), rts),
                alarm_change_dict)
