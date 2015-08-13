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

import operator

from oslo_log import log

from ceilometer.event.storage import base
from ceilometer.event.storage import models
from ceilometer.i18n import _LE
from ceilometer.storage.hbase import base as hbase_base
from ceilometer.storage.hbase import utils as hbase_utils
from ceilometer import utils

LOG = log.getLogger(__name__)


AVAILABLE_CAPABILITIES = {
    'events': {'query': {'simple': True}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


class Connection(hbase_base.Connection, base.Connection):
    """Put the event data into a HBase database

    Collections:

    - events:

      - row_key: timestamp of event's generation + uuid of event
        in format: "%s:%s" % (ts, Event.message_id)
      - Column Families:

        f: contains the following qualifiers:

          - event_type: description of event's type
          - timestamp: time stamp of event generation
          - all traits for this event in format:

            .. code-block:: python

              "%s:%s" % (trait_name, trait_type)
    """

    CAPABILITIES = utils.update_nested(base.Connection.CAPABILITIES,
                                       AVAILABLE_CAPABILITIES)
    STORAGE_CAPABILITIES = utils.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )
    _memory_instance = None

    EVENT_TABLE = "event"

    def __init__(self, url):
        super(Connection, self).__init__(url)

    def upgrade(self):
        tables = [self.EVENT_TABLE]
        column_families = {'f': dict(max_versions=1)}
        with self.conn_pool.connection() as conn:
            hbase_utils.create_tables(conn, tables, column_families)

    def clear(self):
        LOG.debug('Dropping HBase schema...')
        with self.conn_pool.connection() as conn:
            for table in [self.EVENT_TABLE]:
                try:
                    conn.disable_table(table)
                except Exception:
                    LOG.debug('Cannot disable table but ignoring error')
                try:
                    conn.delete_table(table)
                except Exception:
                    LOG.debug('Cannot delete table but ignoring error')

    def record_events(self, event_models):
        """Write the events to Hbase.

        :param event_models: a list of models.Event objects.
        """
        error = None
        with self.conn_pool.connection() as conn:
            events_table = conn.table(self.EVENT_TABLE)
            for event_model in event_models:
                # Row key consists of timestamp and message_id from
                # models.Event or purposes of storage event sorted by
                # timestamp in the database.
                ts = event_model.generated
                row = hbase_utils.prepare_key(
                    hbase_utils.timestamp(ts, reverse=False),
                    event_model.message_id)
                event_type = event_model.event_type
                traits = {}
                if event_model.traits:
                    for trait in event_model.traits:
                        key = hbase_utils.prepare_key(trait.name, trait.dtype)
                        traits[key] = trait.value
                record = hbase_utils.serialize_entry(traits,
                                                     event_type=event_type,
                                                     timestamp=ts,
                                                     raw=event_model.raw)
                try:
                    events_table.put(row, record)
                except Exception as ex:
                    LOG.exception(_LE("Failed to record event: %s") % ex)
                    error = ex
        if error:
            raise error

    def get_events(self, event_filter, limit=None):
        """Return an iter of models.Event objects.

        :param event_filter: storage.EventFilter object, consists of filters
          for events that are stored in database.
        """
        if limit == 0:
            return
        q, start, stop = hbase_utils.make_events_query_from_filter(
            event_filter)
        with self.conn_pool.connection() as conn:
            events_table = conn.table(self.EVENT_TABLE)

            gen = events_table.scan(filter=q, row_start=start, row_stop=stop,
                                    limit=limit)

        for event_id, data in gen:
            traits = []
            events_dict = hbase_utils.deserialize_entry(data)[0]
            for key, value in events_dict.items():
                if isinstance(key, tuple):
                    trait_name, trait_dtype = key
                    traits.append(models.Trait(name=trait_name,
                                               dtype=int(trait_dtype),
                                               value=value))
            ts, mess = event_id.split(':')

            yield models.Event(
                message_id=hbase_utils.unquote(mess),
                event_type=events_dict['event_type'],
                generated=events_dict['timestamp'],
                traits=sorted(traits,
                              key=operator.attrgetter('dtype')),
                raw=events_dict['raw']
            )

    def get_event_types(self):
        """Return all event types as an iterable of strings."""
        with self.conn_pool.connection() as conn:
            events_table = conn.table(self.EVENT_TABLE)
            gen = events_table.scan()

        event_types = set()
        for event_id, data in gen:
            events_dict = hbase_utils.deserialize_entry(data)[0]
            for key, value in events_dict.items():
                if not isinstance(key, tuple) and key.startswith('event_type'):
                    if value not in event_types:
                        event_types.add(value)
                        yield value

    def get_trait_types(self, event_type):
        """Return a dictionary containing the name and data type of the trait.

        Only trait types for the provided event_type are returned.

        :param event_type: the type of the Event
        """

        q = hbase_utils.make_query(event_type=event_type)
        trait_names = set()
        with self.conn_pool.connection() as conn:
            events_table = conn.table(self.EVENT_TABLE)
            gen = events_table.scan(filter=q)
        for event_id, data in gen:
            events_dict = hbase_utils.deserialize_entry(data)[0]
            for key, value in events_dict.items():
                if isinstance(key, tuple):
                    trait_name, trait_type = key
                    if trait_name not in trait_names:
                        # Here we check that our method return only unique
                        # trait types, for ex. if it is found the same trait
                        # types in different events with equal event_type,
                        # method will return only one trait type. It is
                        # proposed that certain trait name could have only one
                        # trait type.
                        trait_names.add(trait_name)
                        data_type = models.Trait.type_names[int(trait_type)]
                        yield {'name': trait_name, 'data_type': data_type}

    def get_traits(self, event_type, trait_type=None):
        """Return all trait instances associated with an event_type.

        If trait_type is specified, only return instances of that trait type.
        :param event_type: the type of the Event to filter by
        :param trait_type: the name of the Trait to filter by
        """
        q = hbase_utils.make_query(event_type=event_type,
                                   trait_type=trait_type)
        with self.conn_pool.connection() as conn:
            events_table = conn.table(self.EVENT_TABLE)
            gen = events_table.scan(filter=q)
        for event_id, data in gen:
            events_dict = hbase_utils.deserialize_entry(data)[0]
            for key, value in events_dict.items():
                if isinstance(key, tuple):
                    trait_name, trait_type = key
                    yield models.Trait(name=trait_name,
                                       dtype=int(trait_type), value=value)
