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
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer.storage.hbase import utils as hbase_utils
from ceilometer.storage import impl_hbase as base
from ceilometer import utils

LOG = log.getLogger(__name__)


AVAILABLE_CAPABILITIES = {
    'events': {'query': {'simple': True}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


class Connection(base.Connection):
    """Put the event data into a HBase database

    Collections:

    - events:

      - row_key: timestamp of event's generation + uuid of event
        in format: "%s+%s" % (ts, Event.message_id)
      - Column Families:

        f: contains the following qualifiers:

          - event_type: description of event's type
          - timestamp: time stamp of event generation
          - all traits for this event in format:

            .. code-block:: python

              "%s+%s" % (trait_name, trait_type)
    """

    CAPABILITIES = utils.update_nested(base.Connection.CAPABILITIES,
                                       AVAILABLE_CAPABILITIES)
    STORAGE_CAPABILITIES = utils.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )
    _memory_instance = None

    EVENT_TABLE = "event"

    def upgrade(self):
        tables = [self.EVENT_TABLE]
        column_families = {'f': dict(max_versions=1)}
        with self.conn_pool.connection() as conn:
            hbase_utils.create_tables(conn, tables, column_families)

    def clear(self):
        LOG.debug(_('Dropping HBase schema...'))
        with self.conn_pool.connection() as conn:
            for table in [self.EVENT_TABLE]:
                try:
                    conn.disable_table(table)
                except Exception:
                    LOG.debug(_('Cannot disable table but ignoring error'))
                try:
                    conn.delete_table(table)
                except Exception:
                    LOG.debug(_('Cannot delete table but ignoring error'))
