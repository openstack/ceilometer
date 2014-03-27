# -*- encoding: utf-8 -*-
#
# Copyright © 2012, 2013 Dell Inc.
#
# Author: Stas Maksimov <Stanislav_M@dell.com>
# Author: Shengjie Min <Shengjie_Min@dell.com>
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
import copy
import datetime
import hashlib
import itertools
import json
import os
import re
import six.moves.urllib.parse as urlparse

import bson.json_util
import happybase

from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import network_utils
from ceilometer.openstack.common import timeutils
from ceilometer import storage
from ceilometer.storage import base
from ceilometer.storage import models
from ceilometer import utils

LOG = log.getLogger(__name__)


class HBaseStorage(base.StorageEngine):
    """Put the data into a HBase database

    Collections:

    - user
      - { _id: user id
          s_source_name: each source reported for user is stored with prefix s_
                         the value of each entry is '1'
          sources: this field contains the first source reported for user.
                   This data is not used but stored for simplification of impl
          }
    - project
      - { _id: project id
          s_source_name: the same as for users
          sources: the same as for users
          }
    - meter
      - {_id_reverted_ts: row key is constructed in this way for efficient
                          filtering
         parsed_info_from_incoming_data: e.g. counter_name, counter_type
         resource_metadata: raw metadata for corresponding resource
         r_metadata_name: flattened metadata for corresponding resource
         message: raw incoming data
         recorded_at: when the sample has been recorded
         source: source for the sample
        }
    - resource
      - the metadata for resources
      - { _id: uuid of resource,
          metadata: raw metadata dictionaries
          r_metadata: flattened metadata fir quick filtering
          timestamp: datetime of last update
          user_id: uuid
          project_id: uuid
          meter: [ array of {counter_name: string, counter_type: string} ]
          source: source of resource
        }
    - alarm
      - the raw incoming alarm data
    - alarm_h
      - raw incoming alarm_history data. Timestamp becomes now()
        if not determined
    """

    @staticmethod
    def get_connection(conf):
        """Return a Connection instance based on the configuration settings.
        """
        return Connection(conf)


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


class Connection(base.Connection):
    """HBase connection.
    """

    _memory_instance = None

    PROJECT_TABLE = "project"
    USER_TABLE = "user"
    RESOURCE_TABLE = "resource"
    METER_TABLE = "meter"
    ALARM_TABLE = "alarm"
    ALARM_HISTORY_TABLE = "alarm_h"

    def __init__(self, conf):
        """Hbase Connection Initialization."""
        opts = self._parse_connection_url(conf.database.connection)

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
                    Connection._memory_instance = MConnectionPool()
                self.conn_pool = Connection._memory_instance
        else:
            self.conn_pool = self._get_connection_pool(opts)

        self.CAPABILITIES = utils.update_nested(self.DEFAULT_CAPABILITIES,
                                                AVAILABLE_CAPABILITIES)

    def upgrade(self):
        with self.conn_pool.connection() as conn:
            conn.create_table(self.PROJECT_TABLE, {'f': dict()})
            conn.create_table(self.USER_TABLE, {'f': dict()})
            conn.create_table(self.RESOURCE_TABLE, {'f': dict()})
            conn.create_table(self.METER_TABLE, {'f': dict()})
            conn.create_table(self.ALARM_TABLE, {'f': dict()})
            conn.create_table(self.ALARM_HISTORY_TABLE, {'f': dict()})

    def clear(self):
        LOG.debug(_('Dropping HBase schema...'))
        with self.conn_pool.connection() as conn:
            for table in [self.PROJECT_TABLE,
                          self.USER_TABLE,
                          self.RESOURCE_TABLE,
                          self.METER_TABLE,
                          self.ALARM_TABLE,
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
        result = network_utils.urlsplit(url)
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
        alarm_to_store = serialize_entry(alarm.as_dict())
        with self.conn_pool.connection() as conn:
            alarm_table = conn.table(self.ALARM_TABLE)
            alarm_table.put(_id, alarm_to_store)
            stored_alarm = deserialize_entry(alarm_table.row(_id))[0]
        return models.Alarm(**stored_alarm)

    create_alarm = update_alarm

    def delete_alarm(self, alarm_id):
        with self.conn_pool.connection() as conn:
            alarm_table = conn.table(self.ALARM_TABLE)
            alarm_table.delete(alarm_id)

    def get_alarms(self, name=None, user=None,
                   project=None, enabled=None, alarm_id=None, pagination=None):

        if pagination:
            raise NotImplementedError('Pagination not implemented')

        q = make_query(alarm_id=alarm_id, name=name, enabled=enabled,
                       user_id=user, project_id=project)

        with self.conn_pool.connection() as conn:
            alarm_table = conn.table(self.ALARM_TABLE)
            gen = alarm_table.scan(filter=q)
            for ignored, data in gen:
                stored_alarm = deserialize_entry(data)[0]
                yield models.Alarm(**stored_alarm)

    def get_alarm_changes(self, alarm_id, on_behalf_of,
                          user=None, project=None, type=None,
                          start_timestamp=None, start_timestamp_op=None,
                          end_timestamp=None, end_timestamp_op=None):
        q = make_query(alarm_id=alarm_id, on_behalf_of=on_behalf_of, type=type,
                       user_id=user, project_id=project)
        start_row, end_row = make_timestamp_query(
            _make_general_rowkey_scan,
            start=start_timestamp, start_op=start_timestamp_op,
            end=end_timestamp, end_op=end_timestamp_op, bounds_only=True,
            some_id=alarm_id)
        with self.conn_pool.connection() as conn:
            alarm_history_table = conn.table(self.ALARM_HISTORY_TABLE)
            gen = alarm_history_table.scan(filter=q, row_start=start_row,
                                           row_stop=end_row)
            for ignored, data in gen:
                stored_entry = deserialize_entry(data)[0]
                yield models.AlarmChange(**stored_entry)

    def record_alarm_change(self, alarm_change):
        """Record alarm change event.
        """
        alarm_change_dict = serialize_entry(alarm_change)
        ts = alarm_change.get('timestamp') or datetime.datetime.now()
        rts = reverse_timestamp(ts)
        with self.conn_pool.connection() as conn:
            alarm_history_table = conn.table(self.ALARM_HISTORY_TABLE)
            alarm_history_table.put(alarm_change.get('alarm_id') + "_" +
                                    str(rts), alarm_change_dict)

    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter
        """
        with self.conn_pool.connection() as conn:
            project_table = conn.table(self.PROJECT_TABLE)
            user_table = conn.table(self.USER_TABLE)
            resource_table = conn.table(self.RESOURCE_TABLE)
            meter_table = conn.table(self.METER_TABLE)

            # Make sure we know about the user and project
            if data['user_id']:
                self._update_sources(user_table, data['user_id'],
                                     data['source'])
            self._update_sources(project_table, data['project_id'],
                                 data['source'])

            # Get metadata from user's data
            resource_metadata = data.get('resource_metadata', {})
            # Determine the name of new meter
            new_meter = _format_meter_reference(
                data['counter_name'], data['counter_type'],
                data['counter_unit'])
            flatten_result, sources, meters, metadata = \
                deserialize_entry(resource_table.row(data['resource_id']))

            # Update if resource has new information
            if (data['source'] not in sources) or (
                    new_meter not in meters) or (
                    metadata != resource_metadata):
                resource_table.put(data['resource_id'],
                                   serialize_entry(
                                       **{'sources': [data['source']],
                                          'meters': [new_meter],
                                          'metadata': resource_metadata,
                                          'resource_id': data['resource_id'],
                                          'project_id': data['project_id'],
                                          'user_id': data['user_id']}))

            # Rowkey consists of reversed timestamp, meter and an md5 of
            # user+resource+project for purposes of uniqueness
            m = hashlib.md5()
            m.update("%s%s%s" % (data['user_id'], data['resource_id'],
                                 data['project_id']))

            # We use reverse timestamps in rowkeys as they are sorted
            # alphabetically.
            rts = reverse_timestamp(data['timestamp'])
            row = "%s_%d_%s" % (data['counter_name'], rts, m.hexdigest())
            record = serialize_entry(data, **{'metadata': resource_metadata,
                                              'rts': rts,
                                              'message': data,
                                              'recorded_at': timeutils.utcnow(
                                              )})
            meter_table.put(row, record)

    def _update_sources(self, table, id, source):
        user, sources, _, _ = deserialize_entry(table.row(id))
        if source not in sources:
            sources.append(source)
            table.put(id, serialize_entry(user, **{'sources': sources}))

    def get_users(self, source=None):
        """Return an iterable of user id strings.

        :param source: Optional source filter.
        """
        with self.conn_pool.connection() as conn:
            user_table = conn.table(self.USER_TABLE)
            LOG.debug(_("source: %s") % source)
            scan_args = {}
            if source:
                scan_args['columns'] = ['f:s_%s' % source]
            return sorted(key for key, ignored in user_table.scan(**scan_args))

    def get_projects(self, source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """
        with self.conn_pool.connection() as conn:
            project_table = conn.table(self.PROJECT_TABLE)
            LOG.debug(_("source: %s") % source)
            scan_args = {}
            if source:
                scan_args['columns'] = ['f:s_%s' % source]
            return (key for key, ignored in project_table.scan(**scan_args))

    def get_resources(self, user=None, project=None, source=None,
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None,
                      metaquery={}, resource=None, pagination=None):
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

        sample_filter = storage.SampleFilter(
            user=user, project=project,
            start=start_timestamp, start_timestamp_op=start_timestamp_op,
            end=end_timestamp, end_timestamp_op=end_timestamp_op,
            resource=resource, source=source, metaquery=metaquery)
        q, start_row, stop_row = make_sample_query_from_filter(
            sample_filter, require_meter=False)

        with self.conn_pool.connection() as conn:
            meter_table = conn.table(self.METER_TABLE)
            LOG.debug(_("Query Meter table: %s") % q)
            meters = meter_table.scan(filter=q, row_start=start_row,
                                      row_stop=stop_row)
            d_meters = []
            for i, m in meters:
                d_meters.append(deserialize_entry(m))

            # We have to sort on resource_id before we can group by it.
            # According to the itertools documentation a new group is
            # generated when the value of the key function changes
            # (it breaks there).
            meters = sorted(d_meters, key=_resource_id_from_record_tuple)
            for resource_id, r_meters in itertools.groupby(
                    meters, key=_resource_id_from_record_tuple):
                # We need deserialized entry(data[0]) and metadata(data[3])
                meter_rows = [(data[0], data[3]) for data in sorted(
                    r_meters, key=_timestamp_from_record_tuple)]
                latest_data = meter_rows[-1]
                min_ts = meter_rows[0][0]['timestamp']
                max_ts = latest_data[0]['timestamp']
                yield models.Resource(
                    resource_id=resource_id,
                    first_sample_timestamp=min_ts,
                    last_sample_timestamp=max_ts,
                    project_id=latest_data[0]['project_id'],
                    source=latest_data[0]['source'],
                    user_id=latest_data[0]['user_id'],
                    metadata=latest_data[1],
                )

    def get_meters(self, user=None, project=None, resource=None, source=None,
                   metaquery={}, pagination=None):
        """Return an iterable of models.Meter instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional resource filter.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param pagination: Optional pagination query.
        """

        if pagination:
            raise NotImplementedError(_('Pagination not implemented'))
        with self.conn_pool.connection() as conn:
            resource_table = conn.table(self.RESOURCE_TABLE)
            q = make_query(metaquery=metaquery, user_id=user,
                           project_id=project, resource_id=resource,
                           source=source)
            LOG.debug(_("Query Resource table: %s") % q)

            gen = resource_table.scan(filter=q)

            for ignored, data in gen:
                flatten_result, s, m, md = deserialize_entry(data)
                if not m:
                    continue
                # Meter table may have only one "meter" and "source". That's
                # why only first lists element is get in this method
                name, type, unit = m[0].split("!")
                yield models.Meter(
                    name=name,
                    type=type,
                    unit=unit,
                    resource_id=flatten_result['resource_id'],
                    project_id=flatten_result['project_id'],
                    source=s[0] if s else None,
                    user_id=flatten_result['user_id'],
                )

    def get_samples(self, sample_filter, limit=None):
        """Return an iterable of models.Sample instances.

        :param sample_filter: Filter.
        :param limit: Maximum number of results to return.
        """
        with self.conn_pool.connection() as conn:
            meter_table = conn.table(self.METER_TABLE)

            q, start, stop = make_sample_query_from_filter(
                sample_filter, require_meter=False)
            LOG.debug(_("Query Meter Table: %s") % q)
            gen = meter_table.scan(filter=q, row_start=start, row_stop=stop)
            for ignored, meter in gen:
                if limit is not None:
                    if limit == 0:
                        break
                    else:
                        limit -= 1
                d_meter = deserialize_entry(meter)[0]
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
        stat.duration = \
            timeutils.delta_seconds(stat.duration_start,
                                    stat.duration_end)

    def get_meter_statistics(self, sample_filter, period=None, groupby=None,
                             aggregate=None):
        """Return an iterable of models.Statistics instances containing meter
        statistics described by the query parameters.

        The filter must have a meter value set.

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
            q, start, stop = make_sample_query_from_filter(sample_filter)
            meters = map(deserialize_entry, list(meter for (ignored, meter) in
                         meter_table.scan(filter=q, row_start=start,
                                          row_stop=stop)))

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

            if not results or not results[-1].period_start == \
                    period_start:
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

    def get_capabilities(self):
        """Return an dictionary representing the capabilities of this driver.
        """
        return self.CAPABILITIES


###############
# This is a very crude version of "in-memory HBase", which implements just
# enough functionality of HappyBase API to support testing of our driver.
#
class MTable(object):
    """HappyBase.Table mock
    """
    def __init__(self, name, families):
        self.name = name
        self.families = families
        self._rows = {}

    def row(self, key):
        return self._rows.get(key, {})

    def rows(self, keys):
        return ((k, self.row(k)) for k in keys)

    def put(self, key, data):
        self._rows[key] = data

    def delete(self, key):
        del self._rows[key]

    def scan(self, filter=None, columns=[], row_start=None, row_stop=None):
        sorted_keys = sorted(self._rows)
        # copy data between row_start and row_stop into a dict
        rows = {}
        for row in sorted_keys:
            if row_start and row < row_start:
                continue
            if row_stop and row > row_stop:
                break
            rows[row] = copy.copy(self._rows[row])
        if columns:
            ret = {}
            for row in rows.keys():
                data = rows[row]
                for key in data:
                    if key in columns:
                        ret[row] = data
            rows = ret
        elif filter:
            # TODO(jdanjou): we should really parse this properly,
            # but at the moment we are only going to support AND here
            filters = filter.split('AND')
            for f in filters:
                # Extract filter name and its arguments
                g = re.search("(.*)\((.*),?\)", f)
                fname = g.group(1).strip()
                fargs = [s.strip().replace('\'', '')
                         for s in g.group(2).split(',')]
                m = getattr(self, fname)
                if callable(m):
                    # overwrite rows for filtering to take effect
                    # in case of multiple filters
                    rows = m(fargs, rows)
                else:
                    raise NotImplementedError("%s filter is not implemented, "
                                              "you may want to add it!")
        for k in sorted(rows):
            yield k, rows[k]

    @staticmethod
    def SingleColumnValueFilter(args, rows):
        """This method is called from scan() when 'SingleColumnValueFilter'
        is found in the 'filter' argument
        """
        op = args[2]
        column = "%s:%s" % (args[0], args[1])
        value = args[3]
        if value.startswith('binary:'):
            value = value[7:]
        r = {}
        for row in rows:
            data = rows[row]

            if op == '=':
                if column in data and data[column] == value:
                    r[row] = data
            elif op == '<=':
                if column in data and data[column] <= value:
                    r[row] = data
            elif op == '>=':
                if column in data and data[column] >= value:
                    r[row] = data
            else:
                raise NotImplementedError("In-memory "
                                          "SingleColumnValueFilter "
                                          "doesn't support the %s operation "
                                          "yet" % op)
        return r


class MConnectionPool(object):
    def __init__(self):
        self.conn = MConnection()

    def connection(self):
        return self.conn


class MConnection(object):
    """HappyBase.Connection mock
    """
    def __init__(self):
        self.tables = {}

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def open(self):
        LOG.debug(_("Opening in-memory HBase connection"))

    def create_table(self, n, families={}):
        if n in self.tables:
            return self.tables[n]
        t = MTable(n, families)
        self.tables[n] = t
        return t

    def delete_table(self, name, use_prefix=True):
        del self.tables[name]

    def table(self, name):
        return self.create_table(name)


#################################################
# Here be various HBase helpers
def reverse_timestamp(dt):
    """Reverse timestamp so that newer timestamps are represented by smaller
    numbers than older ones.

    Reverse timestamps is a technique used in HBase rowkey design. When period
    queries are required the HBase rowkeys must include timestamps, but as
    rowkeys in HBase are ordered lexicographically, the timestamps must be
    reversed.
    """
    epoch = datetime.datetime(1970, 1, 1)
    td = dt - epoch
    ts = td.microseconds + td.seconds * 1000000 + td.days * 86400000000
    return 0x7fffffffffffffff - ts


def make_timestamp_query(func, start=None, start_op=None, end=None,
                         end_op=None, bounds_only=False, **kwargs):
    """Return a filter start and stop row for filtering and a query
    which based on the fact that CF-name is 'rts'
    :param start: Optional start timestamp
    :param start_op: Optional start timestamp operator, like gt, ge
    :param end: Optional end timestamp
    :param end_op: Optional end timestamp operator, like lt, le
    :param bounds_only: if True than query will not be returned
    :param func: a function that provide a format of row
    :param kwargs: kwargs for :param func
    """
    rts_start, rts_end = get_start_end_rts(start, start_op, end, end_op)
    start_row, end_row = func(rts_start, rts_end, **kwargs)

    if bounds_only:
        return start_row, end_row

    q = []
    # We dont need to dump here because get_start_end_rts returns strings
    if rts_start:
        q.append("SingleColumnValueFilter ('f', 'rts', <=, 'binary:%s')" %
                 rts_start)
    if rts_end:
        q.append("SingleColumnValueFilter ('f', 'rts', >=, 'binary:%s')" %
                 rts_end)

    res_q = None
    if len(q):
        res_q = " AND ".join(q)

    return start_row, end_row, res_q


def get_start_end_rts(start, start_op, end, end_op):

    rts_start = str(reverse_timestamp(start) + 1) if start else ""
    rts_end = str(reverse_timestamp(end) + 1) if end else ""

    #By default, we are using ge for lower bound and lt for upper bound
    if start_op == 'gt':
        rts_start = str(long(rts_start) - 2)
    if end_op == 'le':
        rts_end = str(long(rts_end) - 1)

    return rts_start, rts_end


def make_query(metaquery=None, **kwargs):
    """Return a filter query string based on the selected parameters.

    :param metaquery: optional metaquery dict
    :param kwargs: key-value pairs to filter on. Key should be a real
     column name in db
    """
    q = []
    # Note: we use extended constructor for SingleColumnValueFilter here.
    # It is explicitly specified that entry should not be returned if CF is not
    # found in table.
    for key, value in kwargs.items():
        if value is not None:
            q.append("SingleColumnValueFilter "
                     "('f', '%s', =, 'binary:%s', true, true)" %
                     (key, dump(value)))
    res_q = None
    if len(q):
        res_q = " AND ".join(q)

    if metaquery:
        meta_q = []
        for k, v in metaquery.items():
            meta_q.append(
                "SingleColumnValueFilter ('f', '%s', =, 'binary:%s', "
                "true, true)"
                % ('r_' + k, dump(v)))
        meta_q = " AND ".join(meta_q)
        # join query and metaquery
        if res_q is not None:
            res_q += " AND " + meta_q
        else:
            res_q = meta_q   # metaquery only

    return res_q


def make_sample_query_from_filter(sample_filter, require_meter=True):
    """Return a query dictionary based on the settings in the filter.

    :param sample_filter: SampleFilter instance
    :param require_meter: If true and the filter does not have a meter,
                          raise an error.
    """
    meter = sample_filter.meter
    if not meter and require_meter:
        raise RuntimeError('Missing required meter specifier')
    start_row, end_row, ts_query = make_timestamp_query(
        _make_general_rowkey_scan,
        start=sample_filter.start, start_op=sample_filter.start_timestamp_op,
        end=sample_filter.end, end_op=sample_filter.end_timestamp_op,
        some_id=meter)

    q = make_query(metaquery=sample_filter.metaquery,
                   user_id=sample_filter.user,
                   project_id=sample_filter.project,
                   counter_name=meter,
                   resource_id=sample_filter.resource,
                   source=sample_filter.source,
                   message_id=sample_filter.message_id)

    if q:
        ts_query = (" AND " + ts_query) if ts_query else ""
        res_q = q + ts_query if ts_query else q
    else:
        res_q = ts_query if ts_query else None
    return res_q, start_row, end_row


def _make_general_rowkey_scan(rts_start=None, rts_end=None, some_id=None):
    """If it's filter on some_id without start and end,
        start_row = some_id while end_row = some_id + MAX_BYTE
    """
    if some_id is None:
        return None, None
    if not rts_start:
        rts_start = chr(127)
    end_row = "%s_%s" % (some_id, rts_start)
    start_row = "%s_%s" % (some_id, rts_end)

    return start_row, end_row


def _format_meter_reference(counter_name, counter_type, counter_unit):
    """Format reference to meter data.
    """
    return "%s!%s!%s" % (counter_name, counter_type, counter_unit)


def _timestamp_from_record_tuple(record):
    """Extract timestamp from HBase tuple record
    """
    return record[0]['timestamp']


def _resource_id_from_record_tuple(record):
    """Extract resource_id from HBase tuple record
    """
    return record[0]['resource_id']


def deserialize_entry(entry, get_raw_meta=True):
    """Return a list of flatten_result, sources, meters and metadata
    flatten_result contains a dict of simple structures such as 'resource_id':1
    sources/meters are the lists of sources and meters correspondingly.
    metadata is metadata dict. This dict may be returned as flattened if
    get_raw_meta is False.

    :param entry: entry from HBase, without row name and timestamp
    :param get_raw_meta: If true then raw metadata will be returned
                         If False metadata will be constructed from
                         'f:r_metadata.' fields
    """
    flatten_result = {}
    sources = []
    meters = []
    metadata_flattened = {}
    for k, v in entry.items():
        if k.startswith('f:s_'):
            sources.append(k[4:])
        elif k.startswith('f:m_'):
            meters.append(k[4:])
        elif k.startswith('f:r_metadata.'):
            metadata_flattened[k[len('f:r_metadata.'):]] = load(v)
        else:
            flatten_result[k[2:]] = load(v)
    if get_raw_meta:
        metadata = flatten_result.get('metadata', {})
    else:
        metadata = metadata_flattened

    return flatten_result, sources, meters, metadata


def serialize_entry(data={}, **kwargs):
    """Return a dict that is ready to be stored to HBase

    :param data: dict to be serialized
    :param kwargs: additional args
    """
    entry_dict = copy.copy(data)
    entry_dict.update(**kwargs)

    result = {}
    for k, v in entry_dict.items():
        if k == 'sources':
            # user and project tables may contain several sources and meters
            # that's why we store it separately as pairs "source/meter name:1".
            # Resource and meter table contain only one and it's possible
            # to store pairs like "source/meter:source name/meter name". But to
            # keep things simple it's possible to store all variants in all
            # tables because it doesn't break logic and overhead is not too big
            for source in v:
                result['f:s_%s' % source] = dump('1')
            if v:
                result['f:source'] = dump(v[0])
        elif k == 'meters':
            for meter in v:
                result['f:m_%s' % meter] = dump('1')
        elif k == 'metadata':
            # keep raw metadata as well as flattened to provide
            # capability with API v2. It will be flattened in another
            # way on API level. But we need flattened too for quick filtering.
            flattened_meta = dump_metadata(v)
            for k, m in flattened_meta.items():
                result['f:r_metadata.' + k] = dump(m)
            result['f:metadata'] = dump(v)
        else:
            result['f:' + k] = dump(v)
    return result


def dump_metadata(meta):
    resource_metadata = {}
    for key, v in utils.dict_to_keyval(meta):
        resource_metadata[key] = v
    return resource_metadata


def dump(data):
    return json.dumps(data, default=bson.json_util.default)


def load(data):
    return json.loads(data, object_hook=object_hook)


# We don't want to have tzinfo in decoded json.This object_hook is
# overwritten json_util.object_hook for $date
def object_hook(dct):
    if "$date" in dct:
        dt = bson.json_util.object_hook(dct)
        return dt.replace(tzinfo=None)
    return bson.json_util.object_hook(dct)
