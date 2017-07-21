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
import time

from oslo_log import log
from oslo_utils import timeutils

import ceilometer
from ceilometer.storage import base
from ceilometer.storage.hbase import base as hbase_base
from ceilometer.storage.hbase import migration as hbase_migration
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
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


class Connection(hbase_base.Connection, base.Connection):
    """Put the metering data into a HBase database

    Collections:

    - meter (describes sample actually):

      - row-key: consists of reversed timestamp, meter and a message uuid
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
          - all meters with prefix 'm' for this resource in format:

            .. code-block:: python

              "%s:%s:%s:%s:%s" % (rts, source, counter_name, counter_type,
              counter_unit)
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

    def upgrade(self):
        tables = [self.RESOURCE_TABLE, self.METER_TABLE]
        column_families = {'f': dict(max_versions=1)}
        with self.conn_pool.connection() as conn:
            hbase_utils.create_tables(conn, tables, column_families)
            hbase_migration.migrate_tables(conn, tables)

    def clear(self):
        LOG.debug('Dropping HBase schema...')
        with self.conn_pool.connection() as conn:
            for table in [self.RESOURCE_TABLE,
                          self.METER_TABLE]:
                try:
                    conn.disable_table(table)
                except Exception:
                    LOG.debug('Cannot disable table but ignoring error')
                try:
                    conn.delete_table(table)
                except Exception:
                    LOG.debug('Cannot delete table but ignoring error')

    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
          ceilometer.publisher.utils.meter_message_from_counter
        """

        # We must not record thing.
        data.pop("monotonic_time", None)

        with self.conn_pool.connection() as conn:
            resource_table = conn.table(self.RESOURCE_TABLE)
            meter_table = conn.table(self.METER_TABLE)

            resource_metadata = data.get('resource_metadata', {})
            # Determine the name of new meter
            rts = hbase_utils.timestamp(data['timestamp'])
            new_meter = hbase_utils.prepare_key(
                rts, data['source'], data['counter_name'],
                data['counter_type'], data['counter_unit'])

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
            resource_table.put(hbase_utils.encode_unicode(data['resource_id']),
                               resource, ts)

            # Rowkey consists of reversed timestamp, meter and a
            # message uuid for purposes of uniqueness
            row = hbase_utils.prepare_key(data['counter_name'], rts,
                                          data['message_id'])
            record = hbase_utils.serialize_entry(
                data, **{'source': data['source'], 'rts': rts,
                         'message': data, 'recorded_at': timeutils.utcnow()})
            meter_table.put(row, record)

    def get_resources(self, user=None, project=None, source=None,
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None,
                      metaquery=None, resource=None, limit=None):
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
        :param limit: Maximum number of results to return.
        """
        if limit == 0:
            return
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
            LOG.debug("Query Resource table: %s", q)
            for resource_id, data in resource_table.scan(filter=q,
                                                         limit=limit):
                f_res, meters, md = hbase_utils.deserialize_entry(
                    data)
                resource_id = hbase_utils.encode_unicode(resource_id)
                # Unfortunately happybase doesn't keep ordered result from
                # HBase. So that's why it's needed to find min and max
                # manually
                first_ts = min(meters, key=operator.itemgetter(1))[1]
                last_ts = max(meters, key=operator.itemgetter(1))[1]
                source = meters[0][0][1]
                # If we use QualifierFilter then HBase returns only
                # qualifiers filtered by. It will not return the whole entry.
                # That's why if we need to ask additional qualifiers manually.
                if 'project_id' not in f_res and 'user_id' not in f_res:
                    row = resource_table.row(
                        resource_id, columns=['f:project_id', 'f:user_id',
                                              'f:resource_metadata'])
                    f_res, _m, md = hbase_utils.deserialize_entry(row)
                yield models.Resource(
                    resource_id=resource_id,
                    first_sample_timestamp=first_ts,
                    last_sample_timestamp=last_ts,
                    project_id=f_res['project_id'],
                    source=source,
                    user_id=f_res['user_id'],
                    metadata=md)

    def get_meters(self, user=None, project=None, resource=None, source=None,
                   metaquery=None, limit=None, unique=False):
        """Return an iterable of models.Meter instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional resource filter.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param limit: Maximum number of results to return.
        :param unique: If set to true, return only unique meter information.
        """
        if limit == 0:
            return

        metaquery = metaquery or {}

        with self.conn_pool.connection() as conn:
            resource_table = conn.table(self.RESOURCE_TABLE)
            q = hbase_utils.make_query(metaquery=metaquery, user_id=user,
                                       project_id=project,
                                       resource_id=resource,
                                       source=source)
            LOG.debug("Query Resource table: %s", q)

            gen = resource_table.scan(filter=q)
            # We need result set to be sure that user doesn't receive several
            # same meters. Please see bug
            # https://bugs.launchpad.net/ceilometer/+bug/1301371
            result = set()
            for ignored, data in gen:
                flatten_result, meters, md = hbase_utils.deserialize_entry(
                    data)
                for m in meters:
                    if limit and len(result) >= limit:
                        return
                    _m_rts, m_source, name, m_type, unit = m[0]
                    if unique:
                        meter_dict = {'name': name,
                                      'type': m_type,
                                      'unit': unit,
                                      'resource_id': None,
                                      'project_id': None,
                                      'user_id': None,
                                      'source': None}
                    else:
                        meter_dict = {'name': name,
                                      'type': m_type,
                                      'unit': unit,
                                      'resource_id':
                                          flatten_result['resource_id'],
                                      'project_id':
                                          flatten_result['project_id'],
                                      'user_id':
                                          flatten_result['user_id']}

                    frozen_meter = frozenset(meter_dict.items())
                    if frozen_meter in result:
                        continue
                    result.add(frozen_meter)
                    if not unique:
                        meter_dict.update({'source': m_source
                                           if m_source else None})

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
            LOG.debug("Query Meter Table: %s", q)
            gen = meter_table.scan(filter=q, row_start=start, row_stop=stop,
                                   limit=limit, columns=columns)
            for ignored, meter in gen:
                d_meter = hbase_utils.deserialize_entry(meter)[0]
                d_meter['message']['counter_volume'] = (
                    float(d_meter['message']['counter_volume']))
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
            raise ceilometer.NotImplementedError("Group by not implemented.")

        if aggregate:
            raise ceilometer.NotImplementedError(
                'Selectable aggregates not implemented')

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

        if sample_filter.start_timestamp:
            start_time = sample_filter.start_timestamp
        elif meters:
            start_time = meters[-1][0]['timestamp']
        else:
            start_time = None

        if sample_filter.end_timestamp:
            end_time = sample_filter.end_timestamp
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
