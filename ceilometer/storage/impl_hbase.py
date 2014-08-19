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
import operator
import os
import time

import happybase
from oslo.utils import netutils
from oslo.utils import timeutils
from six.moves.urllib import parse as urlparse

from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer.storage import base
from ceilometer.storage.hbase import inmemory as hbase_inmemory
from ceilometer.storage.hbase import utils as hbase_utils
from ceilometer.storage import models
from ceilometer import utils

LOG = log.getLogger(__name__)


AVAILABLE_CAPABILITIES = {
    'meters': {'query': {'simple': True,
                         'metadata': True}},
    'resources': {'query': {'simple': True,
                            'metadata': True}},
    'samples': {'query': {'simple': True,
                          'metadata': True}},
    'statistics': {'query': {'simple': True,
                             'metadata': True},
                   'aggregation': {'standard': True}},
    'events': {'query': {'simple': True}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


class Connection(base.Connection):
    """Put the data into a HBase database

    Collections:

    - meter (describes sample actually):

      - row-key: consists of reversed timestamp, meter and a message signature
        for purposes of uniqueness
      - Column Families:

        f: contains the following qualifiers:

          - counter_name: <name of counter>
          - counter_type: <type of counter>
          - counter_unit: <unit of counter>
          - counter_volume: <volume of counter>
          - message: <raw incoming data>
          - message_id: <id of message>
          - message_signature: <signature of message>
          - resource_metadata: raw metadata for corresponding resource
            of the meter
          - project_id: <id of project>
          - resource_id: <id of resource>
          - user_id: <id of user>
          - recorded_at: <datetime when sample has been recorded (utc.now)>
          - flattened metadata with prefix r_metadata. e.g.::

             f:r_metadata.display_name or f:r_metadata.tag

          - rts: <reversed timestamp of entry>
          - timestamp: <meter's timestamp (came from message)>
          - source for meter with prefix 's'

    - resource:

      - row_key: uuid of resource
      - Column Families:

        f: contains the following qualifiers:

          - resource_metadata: raw metadata for corresponding resource
          - project_id: <id of project>
          - resource_id: <id of resource>
          - user_id: <id of user>
          - flattened metadata with prefix r_metadata. e.g.::

             f:r_metadata.display_name or f:r_metadata.tag

          - sources for all corresponding meters with prefix 's'
          - all meters for this resource in format:

            .. code-block:: python

              "%s+%s+%s!%s!%s" % (rts, source, counter_name, counter_type,
              counter_unit)

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

    RESOURCE_TABLE = "resource"
    METER_TABLE = "meter"
    EVENT_TABLE = "event"

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
            conn.create_table(self.RESOURCE_TABLE, {'f': dict(max_versions=1)})
            conn.create_table(self.METER_TABLE, {'f': dict(max_versions=1)})
            conn.create_table(self.EVENT_TABLE, {'f': dict(max_versions=1)})

    def clear(self):
        LOG.debug(_('Dropping HBase schema...'))
        with self.conn_pool.connection() as conn:
            for table in [self.RESOURCE_TABLE,
                          self.METER_TABLE,
                          self.EVENT_TABLE]:
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

    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
          ceilometer.meter.meter_message_from_counter
        """
        with self.conn_pool.connection() as conn:
            resource_table = conn.table(self.RESOURCE_TABLE)
            meter_table = conn.table(self.METER_TABLE)

            resource_metadata = data.get('resource_metadata', {})
            # Determine the name of new meter
            rts = hbase_utils.timestamp(data['timestamp'])
            new_meter = hbase_utils.format_meter_reference(
                data['counter_name'], data['counter_type'],
                data['counter_unit'], rts, data['source'])

            # TODO(nprivalova): try not to store resource_id
            resource = hbase_utils.serialize_entry(**{
                'source': data['source'],
                'meter': {new_meter: data['timestamp']},
                'resource_metadata': resource_metadata,
                'resource_id': data['resource_id'],
                'project_id': data['project_id'], 'user_id': data['user_id']})
            # Here we put entry in HBase with our own timestamp. This is needed
            # when samples arrive out-of-order
            # If we use timestamp=data['timestamp'] the newest data will be
            # automatically 'on the top'. It is needed to keep metadata
            # up-to-date: metadata from newest samples is considered as actual.
            ts = int(time.mktime(data['timestamp'].timetuple()) * 1000)
            resource_table.put(data['resource_id'], resource, ts)

            # Rowkey consists of reversed timestamp, meter and a
            # message signature for purposes of uniqueness
            row = "%s_%d_%s" % (data['counter_name'], rts,
                                data['message_signature'])
            record = hbase_utils.serialize_entry(
                data, **{'source': data['source'], 'rts': rts,
                         'message': data, 'recorded_at': timeutils.utcnow()})
            meter_table.put(row, record)

    def get_resources(self, user=None, project=None, source=None,
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None,
                      metaquery=None, resource=None, pagination=None):
        """Return an iterable of models.Resource instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param source: Optional source filter.
        :param start_timestamp: Optional modified timestamp start range.
        :param start_timestamp_op: Optional start time operator, like ge, gt.
        :param end_timestamp: Optional modified timestamp end range.
        :param end_timestamp_op: Optional end time operator, like lt, le.
        :param metaquery: Optional dict with metadata to match on.
        :param resource: Optional resource filter.
        :param pagination: Optional pagination query.
        """
        if pagination:
            raise NotImplementedError('Pagination not implemented')

        q = hbase_utils.make_query(metaquery=metaquery, user_id=user,
                                   project_id=project,
                                   resource_id=resource, source=source)
        q = hbase_utils.make_meter_query_for_resource(start_timestamp,
                                                      start_timestamp_op,
                                                      end_timestamp,
                                                      end_timestamp_op,
                                                      source, q)
        with self.conn_pool.connection() as conn:
            resource_table = conn.table(self.RESOURCE_TABLE)
            LOG.debug(_("Query Resource table: %s") % q)
            for resource_id, data in resource_table.scan(filter=q):
                f_res, sources, meters, md = hbase_utils.deserialize_entry(
                    data)
                # Unfortunately happybase doesn't keep ordered result from
                # HBase. So that's why it's needed to find min and max
                # manually
                first_ts = min(meters, key=operator.itemgetter(1))[1]
                last_ts = max(meters, key=operator.itemgetter(1))[1]
                source = meters[0][0].split('+')[1]
                # If we use QualifierFilter then HBase returnes only
                # qualifiers filtered by. It will not return the whole entry.
                # That's why if we need to ask additional qualifiers manually.
                if 'project_id' not in f_res and 'user_id' not in f_res:
                    row = resource_table.row(
                        resource_id, columns=['f:project_id', 'f:user_id',
                                              'f:resource_metadata'])
                    f_res, _s, _m, md = hbase_utils.deserialize_entry(row)
                yield models.Resource(
                    resource_id=resource_id,
                    first_sample_timestamp=first_ts,
                    last_sample_timestamp=last_ts,
                    project_id=f_res['project_id'],
                    source=source,
                    user_id=f_res['user_id'],
                    metadata=md)

    def get_meters(self, user=None, project=None, resource=None, source=None,
                   metaquery=None, pagination=None):
        """Return an iterable of models.Meter instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional resource filter.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param pagination: Optional pagination query.
        """

        metaquery = metaquery or {}

        if pagination:
            raise NotImplementedError(_('Pagination not implemented'))
        with self.conn_pool.connection() as conn:
            resource_table = conn.table(self.RESOURCE_TABLE)
            q = hbase_utils.make_query(metaquery=metaquery, user_id=user,
                                       project_id=project,
                                       resource_id=resource,
                                       source=source)
            LOG.debug(_("Query Resource table: %s") % q)

            gen = resource_table.scan(filter=q)
            # We need result set to be sure that user doesn't receive several
            # same meters. Please see bug
            # https://bugs.launchpad.net/ceilometer/+bug/1301371
            result = set()
            for ignored, data in gen:
                flatten_result, s, meters, md = hbase_utils.deserialize_entry(
                    data)
                for m in meters:
                    _m_rts, m_source, m_raw = m[0].split("+")
                    name, type, unit = m_raw.split('!')
                    meter_dict = {'name': name,
                                  'type': type,
                                  'unit': unit,
                                  'resource_id': flatten_result['resource_id'],
                                  'project_id': flatten_result['project_id'],
                                  'user_id': flatten_result['user_id']}
                    frozen_meter = frozenset(meter_dict.items())
                    if frozen_meter in result:
                        continue
                    result.add(frozen_meter)
                    meter_dict.update({'source':
                                       m_source if m_source else None})

                    yield models.Meter(**meter_dict)

    def get_samples(self, sample_filter, limit=None):
        """Return an iterable of models.Sample instances.

        :param sample_filter: Filter.
        :param limit: Maximum number of results to return.
        """
        if limit == 0:
            return
        with self.conn_pool.connection() as conn:
            meter_table = conn.table(self.METER_TABLE)
            q, start, stop, columns = (hbase_utils.
                                       make_sample_query_from_filter
                                       (sample_filter, require_meter=False))
            LOG.debug(_("Query Meter Table: %s") % q)
            gen = meter_table.scan(filter=q, row_start=start, row_stop=stop,
                                   limit=limit)
            for ignored, meter in gen:
                d_meter = hbase_utils.deserialize_entry(meter)[0]
                d_meter['message']['recorded_at'] = d_meter['recorded_at']
                yield models.Sample(**d_meter['message'])

    @staticmethod
    def _update_meter_stats(stat, meter):
        """Do the stats calculation on a requested time bucket in stats dict

        :param stats: dict where aggregated stats are kept
        :param index: time bucket index in stats
        :param meter: meter record as returned from HBase
        :param start_time: query start time
        :param period: length of the time bucket
        """
        vol = meter['counter_volume']
        ts = meter['timestamp']
        stat.unit = meter['counter_unit']
        stat.min = min(vol, stat.min or vol)
        stat.max = max(vol, stat.max)
        stat.sum = vol + (stat.sum or 0)
        stat.count += 1
        stat.avg = (stat.sum / float(stat.count))
        stat.duration_start = min(ts, stat.duration_start or ts)
        stat.duration_end = max(ts, stat.duration_end or ts)
        stat.duration = (timeutils.delta_seconds(stat.duration_start,
                                                 stat.duration_end))

    def get_meter_statistics(self, sample_filter, period=None, groupby=None,
                             aggregate=None):
        """Return an iterable of models.Statistics instances.

        Items are containing meter statistics described by the query
        parameters. The filter must have a meter value set.

        .. note::

          Due to HBase limitations the aggregations are implemented
          in the driver itself, therefore this method will be quite slow
          because of all the Thrift traffic it is going to create.
        """
        if groupby:
            raise NotImplementedError("Group by not implemented.")

        if aggregate:
            raise NotImplementedError('Selectable aggregates not implemented')

        with self.conn_pool.connection() as conn:
            meter_table = conn.table(self.METER_TABLE)
            q, start, stop, columns = (hbase_utils.
                                       make_sample_query_from_filter
                                       (sample_filter))
            # These fields are used in statistics' calculating
            columns.extend(['f:timestamp', 'f:counter_volume',
                            'f:counter_unit'])
            meters = map(hbase_utils.deserialize_entry,
                         list(meter for (ignored, meter) in
                              meter_table.scan(
                                  filter=q, row_start=start,
                                  row_stop=stop, columns=columns)))

        if sample_filter.start:
            start_time = sample_filter.start
        elif meters:
            start_time = meters[-1][0]['timestamp']
        else:
            start_time = None

        if sample_filter.end:
            end_time = sample_filter.end
        elif meters:
            end_time = meters[0][0]['timestamp']
        else:
            end_time = None

        results = []

        if not period:
            period = 0
            period_start = start_time
            period_end = end_time

        # As our HBase meters are stored as newest-first, we need to iterate
        # in the reverse order
        for meter in meters[::-1]:
            ts = meter[0]['timestamp']
            if period:
                offset = int(timeutils.delta_seconds(
                    start_time, ts) / period) * period
                period_start = start_time + datetime.timedelta(0, offset)

            if not results or not results[-1].period_start == period_start:
                if period:
                    period_end = period_start + datetime.timedelta(
                        0, period)
                results.append(
                    models.Statistics(unit='',
                                      count=0,
                                      min=0,
                                      max=0,
                                      avg=0,
                                      sum=0,
                                      period=period,
                                      period_start=period_start,
                                      period_end=period_end,
                                      duration=None,
                                      duration_start=None,
                                      duration_end=None,
                                      groupby=None)
                )
            self._update_meter_stats(results[-1], meter[0])
        return results

    def record_events(self, event_models):
        """Write the events to Hbase.

        :param event_models: a list of models.Event objects.
        :return problem_events: a list of events that could not be saved in a
          (reason, event) tuple. From the reasons that are enumerated in
          storage.models.Event only the UNKNOWN_PROBLEM is applicable here.
        """
        problem_events = []

        with self.conn_pool.connection() as conn:
            events_table = conn.table(self.EVENT_TABLE)
            for event_model in event_models:
                # Row key consists of timestamp and message_id from
                # models.Event or purposes of storage event sorted by
                # timestamp in the database.
                ts = event_model.generated
                row = "%d_%s" % (hbase_utils.timestamp(ts, reverse=False),
                                 event_model.message_id)
                event_type = event_model.event_type
                traits = {}
                if event_model.traits:
                    for trait in event_model.traits:
                        key = "%s+%d" % (trait.name, trait.dtype)
                        traits[key] = trait.value
                record = hbase_utils.serialize_entry(traits,
                                                     event_type=event_type,
                                                     timestamp=ts)
                try:
                    events_table.put(row, record)
                except Exception as ex:
                    LOG.debug(_("Failed to record event: %s") % ex)
                    problem_events.append((models.Event.UNKNOWN_PROBLEM,
                                           event_model))
        return problem_events

    def get_events(self, event_filter):
        """Return an iter of models.Event objects.

        :param event_filter: storage.EventFilter object, consists of filters
          for events that are stored in database.
        """
        q, start, stop = hbase_utils.make_events_query_from_filter(
            event_filter)
        with self.conn_pool.connection() as conn:
            events_table = conn.table(self.EVENT_TABLE)

            gen = events_table.scan(filter=q, row_start=start, row_stop=stop)

        for event_id, data in gen:
            traits = []
            events_dict = hbase_utils.deserialize_entry(data)[0]
            for key, value in events_dict.items():
                if (not key.startswith('event_type')
                        and not key.startswith('timestamp')):
                    trait_name, trait_dtype = key.rsplit('+', 1)
                    traits.append(models.Trait(name=trait_name,
                                               dtype=int(trait_dtype),
                                               value=value))
            ts, mess = event_id.split('_', 1)

            yield models.Event(
                message_id=mess,
                event_type=events_dict['event_type'],
                generated=events_dict['timestamp'],
                traits=sorted(traits,
                              key=operator.attrgetter('dtype'))
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
                if key.startswith('event_type'):
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
                if (not key.startswith('event_type') and
                        not key.startswith('timestamp')):
                    trait_name, trait_type = key.rsplit('+', 1)
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
                if (not key.startswith('event_type') and
                        not key.startswith('timestamp')):
                    trait_name, trait_type = key.rsplit('+', 1)
                    yield models.Trait(name=trait_name,
                                       dtype=int(trait_type), value=value)
