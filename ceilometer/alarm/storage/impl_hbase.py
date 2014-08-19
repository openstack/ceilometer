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
"""HBase storage backend
"""
import datetime
import os

import happybase
from oslo.utils import netutils
from six.moves.urllib import parse as urlparse

from ceilometer.alarm.storage import base
from ceilometer.alarm.storage import models
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer.storage.hbase import inmemory as hbase_inmemory
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


class Connection(base.Connection):
    """Put the data into a HBase database

    Collections:

    - alarm:

      - row_key: uuid of alarm
      - Column Families:

        f: contains the raw incoming alarm data

    - alarm_h:

      - row_key: uuid of alarm + "_" + reversed timestamp
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
        """Hbase Connection Initialization."""
        opts = self._parse_connection_url(url)

        if opts['host'] == '__test__':
            url = os.environ.get('CEILOMETER_TEST_HBASE_URL')
            if url:
                # Reparse URL, but from the env variable now
                opts = self._parse_connection_url(url)
                self.conn_pool = self._get_connection_pool(opts)
            else:
                # This is a in-memory usage for unit tests
                if Connection._memory_instance is None:
                    LOG.debug(_('Creating a new in-memory HBase '
                              'Connection object'))
                    Connection._memory_instance = (hbase_inmemory.
                                                   MConnectionPool())
                self.conn_pool = Connection._memory_instance
        else:
            self.conn_pool = self._get_connection_pool(opts)

    def upgrade(self):
        with self.conn_pool.connection() as conn:
            conn.create_table(self.ALARM_TABLE, {'f': dict()})
            conn.create_table(self.ALARM_HISTORY_TABLE, {'f': dict()})

    def clear(self):
        LOG.debug(_('Dropping HBase schema...'))
        with self.conn_pool.connection() as conn:
            for table in [self.ALARM_TABLE,
                          self.ALARM_HISTORY_TABLE]:
                try:
                    conn.disable_table(table)
                except Exception:
                    LOG.debug(_('Cannot disable table but ignoring error'))
                try:
                    conn.delete_table(table)
                except Exception:
                    LOG.debug(_('Cannot delete table but ignoring error'))

    @staticmethod
    def _get_connection_pool(conf):
        """Return a connection pool to the database.

        .. note::

          The tests use a subclass to override this and return an
          in-memory connection pool.
        """
        LOG.debug(_('connecting to HBase on %(host)s:%(port)s') % (
                  {'host': conf['host'], 'port': conf['port']}))
        return happybase.ConnectionPool(size=100, host=conf['host'],
                                        port=conf['port'],
                                        table_prefix=conf['table_prefix'])

    @staticmethod
    def _parse_connection_url(url):
        """Parse connection parameters from a database url.

        .. note::

          HBase Thrift does not support authentication and there is no
          database name, so we are not looking for these in the url.
        """
        opts = {}
        result = netutils.urlsplit(url)
        opts['table_prefix'] = urlparse.parse_qs(
            result.query).get('table_prefix', [None])[0]
        opts['dbtype'] = result.scheme
        if ':' in result.netloc:
            opts['host'], port = result.netloc.split(':')
        else:
            opts['host'] = result.netloc
            port = 9090
        opts['port'] = port and int(port) or 9090
        return opts

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
        with self.conn_pool.connection() as conn:
            alarm_table = conn.table(self.ALARM_TABLE)
            alarm_table.delete(alarm_id)

    def get_alarms(self, name=None, user=None, state=None, meter=None,
                   project=None, enabled=None, alarm_id=None, pagination=None):

        if pagination:
            raise NotImplementedError('Pagination not implemented')
        if meter:
            raise NotImplementedError('Filter by meter not implemented')

        q = hbase_utils.make_query(alarm_id=alarm_id, name=name,
                                   enabled=enabled, user_id=user,
                                   project_id=project, state=state)

        with self.conn_pool.connection() as conn:
            alarm_table = conn.table(self.ALARM_TABLE)
            gen = alarm_table.scan(filter=q)
            for ignored, data in gen:
                stored_alarm = hbase_utils.deserialize_entry(data)[0]
                yield models.Alarm(**stored_alarm)

    def get_alarm_changes(self, alarm_id, on_behalf_of,
                          user=None, project=None, type=None,
                          start_timestamp=None, start_timestamp_op=None,
                          end_timestamp=None, end_timestamp_op=None):
        q = hbase_utils.make_query(alarm_id=alarm_id,
                                   on_behalf_of=on_behalf_of, type=type,
                                   user_id=user, project_id=project)
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
            alarm_history_table.put(alarm_change.get('alarm_id') + "_" +
                                    str(rts), alarm_change_dict)
