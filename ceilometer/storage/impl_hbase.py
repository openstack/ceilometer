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

import happybase

from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import network_utils
from ceilometer.openstack.common import timeutils
from ceilometer.storage import base
from ceilometer.storage import models
from ceilometer import utils

LOG = log.getLogger(__name__)


class HBaseStorage(base.StorageEngine):
    """Put the data into a HBase database

    Collections:

    - user
      - { _id: user id
          source: [ array of source ids reporting for the user ]
          }
    - project
      - { _id: project id
          source: [ array of source ids reporting for the project ]
          }
    - meter
      - the raw incoming data
    - resource
      - the metadata for resources
      - { _id: uuid of resource,
          metadata: metadata dictionaries
          timestamp: datetime of last update
          user_id: uuid
          project_id: uuid
          meter: [ array of {counter_name: string, counter_type: string} ]
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
                self.conn = self._get_connection(opts)
            else:
                # This is a in-memory usage for unit tests
                if Connection._memory_instance is None:
                    LOG.debug(_('Creating a new in-memory HBase '
                              'Connection object'))
                    Connection._memory_instance = MConnection()
                self.conn = Connection._memory_instance
        else:
            self.conn = self._get_connection(opts)
        self.conn.open()

    def upgrade(self):
        self.conn.create_table(self.PROJECT_TABLE, {'f': dict()})
        self.conn.create_table(self.USER_TABLE, {'f': dict()})
        self.conn.create_table(self.RESOURCE_TABLE, {'f': dict()})
        self.conn.create_table(self.METER_TABLE, {'f': dict()})
        self.conn.create_table(self.ALARM_TABLE, {'f': dict()})
        self.conn.create_table(self.ALARM_HISTORY_TABLE, {'f': dict()})

    def clear(self):
        LOG.debug(_('Dropping HBase schema...'))
        for table in [self.PROJECT_TABLE,
                      self.USER_TABLE,
                      self.RESOURCE_TABLE,
                      self.METER_TABLE,
                      self.ALARM_TABLE,
                      self.ALARM_HISTORY_TABLE]:
            try:
                self.conn.disable_table(table)
            except Exception:
                LOG.debug(_('Cannot disable table but ignoring error'))
            try:
                self.conn.delete_table(table)
            except Exception:
                LOG.debug(_('Cannot delete table but ignoring error'))

    @staticmethod
    def _get_connection(conf):
        """Return a connection to the database.

        .. note::

          The tests use a subclass to override this and return an
          in-memory connection.
        """
        LOG.debug(_('connecting to HBase on %(host)s:%(port)s') % (
                  {'host': conf['host'], 'port': conf['port']}))
        return happybase.Connection(host=conf['host'], port=conf['port'],
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
        alarm_table = self.conn.table(self.ALARM_TABLE)

        alarm_to_store = serialize_entry(alarm.as_dict())
        alarm_table.put(_id, alarm_to_store)
        stored_alarm = deserialize_entry(alarm_table.row(_id))
        return models.Alarm(**stored_alarm)

    create_alarm = update_alarm

    def delete_alarm(self, alarm_id):
        alarm_table = self.conn.table(self.ALARM_TABLE)
        alarm_table.delete(alarm_id)

    def get_alarms(self, name=None, user=None,
                   project=None, enabled=None, alarm_id=None, pagination=None):

        if pagination:
            raise NotImplementedError(_('Pagination not implemented'))

        alarm_table = self.conn.table(self.ALARM_TABLE)

        #TODO(nprivalova): to be refactored
        if enabled is not None:
            enabled = json.dumps(enabled)

        q = make_query(require_meter=False, query_only=True,
                       alarm_id=alarm_id, name=name,
                       enabled=enabled, user_id=user, project_id=project)
        gen = alarm_table.scan(filter=q)
        for ignored, data in gen:
            stored_alarm = deserialize_entry(data)
            yield models.Alarm(**stored_alarm)

    def get_alarm_changes(self, alarm_id, on_behalf_of,
                          user=None, project=None, type=None,
                          start_timestamp=None, start_timestamp_op=None,
                          end_timestamp=None, end_timestamp_op=None):
        alarm_history_table = self.conn.table(self.ALARM_HISTORY_TABLE)

        q = make_query(start=start_timestamp,
                       start_op=start_timestamp_op,
                       end=end_timestamp,
                       end_op=end_timestamp_op,
                       require_meter=False, query_only=True,
                       include_rts_in_filters=False, alarm_id=alarm_id,
                       on_behalf_of=on_behalf_of, type=type, user_id=user,
                       project_id=project)
        #TODO(nprivalova): refactor make_query to move this stuff there
        rts_start = str(reverse_timestamp(start_timestamp) + 1) \
            if start_timestamp else ""
        rts_end = str(reverse_timestamp(end_timestamp) + 1) \
            if end_timestamp else ""
        if start_timestamp_op == 'gt':
            rts_start = str(long(rts_start) - 2)
        if end_timestamp_op == 'le':
            rts_end = str(long(rts_end) - 1)

        gen = alarm_history_table.scan(filter=q, row_start=rts_end,
                                       row_stop=rts_start)
        for ignored, data in gen:
            stored_entry = deserialize_entry(data)
            # It is needed to return 'details' field as string
            detail = stored_entry['detail']
            if detail:
                stored_entry['detail'] = json.dumps(detail)
            yield models.AlarmChange(**stored_entry)

    def record_alarm_change(self, alarm_change):
        """Record alarm change event.
        """
        alarm_change_dict = serialize_entry(alarm_change)
        ts = alarm_change.get('timestamp') or datetime.datetime.now()
        rts = reverse_timestamp(ts)

        alarm_history_table = self.conn.table(self.ALARM_HISTORY_TABLE)
        alarm_history_table.put(alarm_change.get('alarm_id') + "_" + str(rts),
                                alarm_change_dict)

    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter
        """
        project_table = self.conn.table(self.PROJECT_TABLE)
        user_table = self.conn.table(self.USER_TABLE)
        resource_table = self.conn.table(self.RESOURCE_TABLE)
        meter_table = self.conn.table(self.METER_TABLE)

        # store metadata fields with prefix "r_" to make filtering on metadata
        # faster
        resource_metadata = {}
        res_meta_copy = data['resource_metadata']
        if res_meta_copy:
            for key, v in utils.dict_to_keyval(res_meta_copy):
                resource_metadata['f:r_metadata.%s' % key] = unicode(v)

        # Make sure we know about the user and project
        if data['user_id']:
            user = user_table.row(data['user_id'])
            sources = _load_hbase_list(user, 's')
            # Update if source is new
            if data['source'] not in sources:
                user['f:s_%s' % data['source']] = "1"
                user_table.put(data['user_id'], user)

        project = project_table.row(data['project_id'])
        sources = _load_hbase_list(project, 's')
        # Update if source is new
        if data['source'] not in sources:
            project['f:s_%s' % data['source']] = "1"
            project_table.put(data['project_id'], project)

        rts = reverse_timestamp(data['timestamp'])

        resource = resource_table.row(data['resource_id'])

        new_meter = _format_meter_reference(
            data['counter_name'], data['counter_type'], data['counter_unit'])
        new_resource = {'f:resource_id': data['resource_id'],
                        'f:project_id': data['project_id'],
                        'f:user_id': data['user_id'],
                        'f:source': data["source"],
                        # store meters with prefix "m_"
                        'f:m_%s' % new_meter: "1"
                        }
        new_resource.update(resource_metadata)

        # Update if resource has new information
        if new_resource != resource:
            meters = _load_hbase_list(resource, 'm')
            if new_meter not in meters:
                new_resource['f:m_%s' % new_meter] = "1"

            resource_table.put(data['resource_id'], new_resource)

        # Rowkey consists of reversed timestamp, meter and an md5 of
        # user+resource+project for purposes of uniqueness
        m = hashlib.md5()
        m.update("%s%s%s" % (data['user_id'], data['resource_id'],
                             data['project_id']))

        # We use reverse timestamps in rowkeys as they are sorted
        # alphabetically.
        row = "%s_%d_%s" % (data['counter_name'], rts, m.hexdigest())

        recorded_at = timeutils.utcnow()

        # Convert timestamp to string as json.dumps won't
        ts = timeutils.strtime(data['timestamp'])
        recorded_at_ts = timeutils.strtime(recorded_at)

        record = {'f:timestamp': ts,
                  'f:counter_name': data['counter_name'],
                  'f:counter_type': data['counter_type'],
                  'f:counter_volume': str(data['counter_volume']),
                  'f:counter_unit': data['counter_unit'],
                  # TODO(shengjie) consider using QualifierFilter
                  # keep dimensions as column qualifier for quicker look up
                  # TODO(shengjie) extra dimensions need to be added as CQ
                  'f:user_id': data['user_id'],
                  'f:project_id': data['project_id'],
                  'f:message_id': data['message_id'],
                  'f:resource_id': data['resource_id'],
                  'f:source': data['source'],
                  'f:recorded_at': recorded_at,
                  # keep raw metadata as well as flattened to provide
                  # capability with API v2. It will be flattened in another
                  # way on API level
                  'f:metadata': data.get('resource_metadata', '{}'),
                  # add in reversed_ts here for time range scan
                  'f:rts': str(rts)
                  }
        # Need to record resource_metadata for more robust filtering.
        record.update(resource_metadata)
        # Don't want to be changing the original data object.
        data = copy.copy(data)
        data['timestamp'] = ts
        data['recorded_at'] = recorded_at_ts
        # Save original meter.
        record['f:message'] = json.dumps(data)
        meter_table.put(row, record)

    def get_users(self, source=None):
        """Return an iterable of user id strings.

        :param source: Optional source filter.
        """
        user_table = self.conn.table(self.USER_TABLE)
        LOG.debug(_("source: %s") % source)
        scan_args = {}
        if source:
            scan_args['columns'] = ['f:s_%s' % source]
        return sorted(key for key, ignored in user_table.scan(**scan_args))

    def get_projects(self, source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """
        project_table = self.conn.table(self.PROJECT_TABLE)
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
            raise NotImplementedError(_('Pagination not implemented'))

        def make_resource(data, first_ts, last_ts):
            """Transform HBase fields to Resource model."""
            return models.Resource(
                resource_id=data['f:resource_id'],
                first_sample_timestamp=first_ts,
                last_sample_timestamp=last_ts,
                project_id=data['f:project_id'],
                source=data['f:source'],
                user_id=data['f:user_id'],
                metadata=data['f:metadata'],
            )
        meter_table = self.conn.table(self.METER_TABLE)

        q, start_row, stop_row = make_query(user_id=user,
                                            project_id=project,
                                            source=source,
                                            resource_id=resource,
                                            start=start_timestamp,
                                            start_op=start_timestamp_op,
                                            end=end_timestamp,
                                            end_op=end_timestamp_op,
                                            metaquery=metaquery,
                                            require_meter=False,
                                            query_only=False)
        LOG.debug(_("Query Meter table: %s") % q)
        meters = meter_table.scan(filter=q, row_start=start_row,
                                  row_stop=stop_row)

        # We have to sort on resource_id before we can group by it. According
        # to the itertools documentation a new group is generated when the
        # value of the key function changes (it breaks there).
        meters = sorted(meters, key=_resource_id_from_record_tuple)

        for resource_id, r_meters in itertools.groupby(
                meters, key=_resource_id_from_record_tuple):
            meter_rows = [data[1] for data in sorted(
                r_meters, key=_timestamp_from_record_tuple)]

            latest_data = meter_rows[-1]
            min_ts = timeutils.parse_strtime(meter_rows[0]['f:timestamp'])
            max_ts = timeutils.parse_strtime(latest_data['f:timestamp'])
            yield make_resource(
                latest_data,
                min_ts,
                max_ts
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
        resource_table = self.conn.table(self.RESOURCE_TABLE)
        q = make_query(user_id=user, project_id=project, resource_id=resource,
                       source=source, metaquery=metaquery,
                       require_meter=False, query_only=True)
        LOG.debug(_("Query Resource table: %s") % q)

        gen = resource_table.scan(filter=q)

        for ignored, data in gen:
            # Meter columns are stored like this:
            # "m_{counter_name}|{counter_type}|{counter_unit}" => "1"
            # where 'm' is a prefix (m for meter), value is always set to 1
            meter = None
            for m in data:
                if m.startswith('f:m_'):
                    meter = m
                    break
            if meter is None:
                continue
            name, type, unit = meter[4:].split("!")
            yield models.Meter(
                name=name,
                type=type,
                unit=unit,
                resource_id=data['f:resource_id'],
                project_id=data['f:project_id'],
                source=data['f:source'],
                user_id=data['f:user_id'],
            )

    @staticmethod
    def _make_sample(data):
        """Transform HBase fields to Sample model."""
        data = json.loads(data['f:message'])
        data['timestamp'] = timeutils.parse_strtime(data['timestamp'])
        data['recorded_at'] = timeutils.parse_strtime(data['recorded_at'])
        return models.Sample(**data)

    def get_samples(self, sample_filter, limit=None):
        """Return an iterable of models.Sample instances.

        :param sample_filter: Filter.
        :param limit: Maximum number of results to return.
        """

        meter_table = self.conn.table(self.METER_TABLE)

        q, start, stop = make_query_from_filter(sample_filter,
                                                require_meter=False)
        LOG.debug(_("Query Meter Table: %s") % q)
        gen = meter_table.scan(filter=q, row_start=start, row_stop=stop)
        for ignored, meter in gen:
            if limit is not None:
                if limit == 0:
                    break
                else:
                    limit -= 1
            yield self._make_sample(meter)

    @staticmethod
    def _update_meter_stats(stat, meter):
        """Do the stats calculation on a requested time bucket in stats dict

        :param stats: dict where aggregated stats are kept
        :param index: time bucket index in stats
        :param meter: meter record as returned from HBase
        :param start_time: query start time
        :param period: length of the time bucket
        """
        vol = int(meter['f:counter_volume'])
        ts = timeutils.parse_strtime(meter['f:timestamp'])
        stat.unit = meter['f:counter_unit']
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

    def get_meter_statistics(self, sample_filter, period=None, groupby=None):
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

        meter_table = self.conn.table(self.METER_TABLE)

        q, start, stop = make_query_from_filter(sample_filter)

        meters = list(meter for (ignored, meter) in
                      meter_table.scan(filter=q, row_start=start,
                                       row_stop=stop)
                      )

        if sample_filter.start:
            start_time = sample_filter.start
        elif meters:
            start_time = timeutils.parse_strtime(meters[-1]['f:timestamp'])
        else:
            start_time = None

        if sample_filter.end:
            end_time = sample_filter.end
        elif meters:
            end_time = timeutils.parse_strtime(meters[0]['f:timestamp'])
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
            ts = timeutils.parse_strtime(meter['f:timestamp'])
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
            self._update_meter_stats(results[-1], meter)
        return results


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
                fargs = [s.strip().replace('\'', '').replace('\"', '')
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


class MConnection(object):
    """HappyBase.Connection mock
    """
    def __init__(self):
        self.tables = {}

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


def make_query(meter=None, start=None, start_op=None,
               end=None, end_op=None, metaquery=None,
               require_meter=True, query_only=False,
               include_rts_in_filters=True, **kwargs):
    """Return a filter query string based on the selected parameters.

    :param meter: Optional counter-name
    :param start: Optional start timestamp
    :param start_op: Optional start timestamp operator, like gt, ge
    :param end: Optional end timestamp
    :param end_op: Optional end timestamp operator, like lt, le
    :param require_meter: If true and the filter does not have a meter,
            raise an error.
    :param query_only: If true only returns the filter query,
            otherwise also returns start and stop rowkeys
    """
    q = []

    for key, value in kwargs.iteritems():
        if value is not None:
            q.append("SingleColumnValueFilter "
                     "('f', '%s', =, 'binary:%s')" % (key, value))

    start_row, end_row = "", ""
    rts_start = str(reverse_timestamp(start) + 1) if start else ""
    rts_end = str(reverse_timestamp(end) + 1) if end else ""

    #By default, we are using ge for lower bound and lt for upper bound
    if start_op == 'gt':
        rts_start = str(long(rts_start) - 2)
    if end_op == 'le':
        rts_end = str(long(rts_end) - 1)

    # when start_time and end_time is provided,
    #    if it's filtered by meter,
    #         rowkey will be used in the query;
    #    else it's non meter filter query(e.g. project_id, user_id etc),
    #         SingleColumnValueFilter against rts will be appended to the query
    #    query other tables should have no start and end passed in
    if meter:
        start_row, end_row = _make_rowkey_scan(meter, rts_start, rts_end)
        q.append("SingleColumnValueFilter "
                 "('f', 'counter_name', =, 'binary:%s')" % meter)
    elif require_meter:
        raise RuntimeError('Missing required meter specifier')
    elif include_rts_in_filters:
        if rts_start:
            q.append("SingleColumnValueFilter ('f', 'rts', <=, 'binary:%s')" %
                     rts_start)
        if rts_end:
            q.append("SingleColumnValueFilter ('f', 'rts', >=, 'binary:%s')" %
                     rts_end)

    res_q = None
    if len(q):
        res_q = " AND ".join(q)

    if metaquery:
        meta_q = []
        for k, v in metaquery.items():
            meta_q.append(
                "SingleColumnValueFilter ('f', '%s', =, 'binary:%s')"
                % ('r_' + k, v))
        meta_q = " AND ".join(meta_q)
        # join query and metaquery
        if res_q is not None:
            res_q += " AND " + meta_q
        else:
            res_q = meta_q   # metaquery only

    if query_only:
        return res_q
    else:
        return res_q, start_row, end_row


def make_query_from_filter(sample_filter, require_meter=True):
    """Return a query dictionary based on the settings in the filter.

    :param sample_filter: SampleFilter instance
    :param require_meter: If true and the filter does not have a meter,
                          raise an error.
    """
    return make_query(user_id=sample_filter.user,
                      project_id=sample_filter.project,
                      meter=sample_filter.meter,
                      resource_id=sample_filter.resource,
                      source=sample_filter.source,
                      start=sample_filter.start,
                      start_op=sample_filter.start_timestamp_op,
                      end=sample_filter.end,
                      end_op=sample_filter.end_timestamp_op,
                      metaquery=sample_filter.metaquery,
                      message_id=sample_filter.message_id,
                      require_meter=require_meter)


def _make_rowkey_scan(meter, rts_start=None, rts_end=None):
    """If it's meter filter without start and end,
        start_row = meter while end_row = meter + MAX_BYTE
    """
    if not rts_start:
        rts_start = chr(127)
    end_row = "%s_%s" % (meter, rts_start)
    start_row = "%s_%s" % (meter, rts_end)

    return start_row, end_row


def _load_hbase_list(d, prefix):
    """Deserialise dict stored as HBase column family
    """
    ret = []
    prefix = 'f:%s_' % prefix
    for key in (k for k in d if k.startswith(prefix)):
        ret.append(key[len(prefix):])
    return ret


def _format_meter_reference(counter_name, counter_type, counter_unit):
    """Format reference to meter data.
    """
    return "%s!%s!%s" % (counter_name, counter_type, counter_unit)


def _timestamp_from_record_tuple(record):
    """Extract timestamp from HBase tuple record
    """
    return timeutils.parse_strtime(record[1]['f:timestamp'])


def _resource_id_from_record_tuple(record):
    """Extract resource_id from HBase tuple record
    """
    return record[1]['f:resource_id']


#TODO(nprivalova): to be refactored, will be used everywhere in impl_hbase
# without additional ifs
def serialize_entry(entry_from_user):
    result_dict = copy.copy(entry_from_user)
    keys = result_dict.keys()
    for key in keys:
        val = result_dict[key]
        if isinstance(val, datetime.datetime):
            val = timeutils.strtime(val)
        if not isinstance(val, basestring):
            val = json.dumps(val)
        result_dict['f:' + key] = val
        del result_dict[key]
    return result_dict


def deserialize_entry(stored_entry):
    result_entry = copy.copy(stored_entry)
    keys = result_entry.keys()
    for key in keys:
        val = result_entry[key]
        try:
            val = json.loads(val)
        except ValueError:
            pass
        if "timestamp" in key and val:
            val = timeutils.parse_strtime(val)
        # There is no int in wsme models
        if isinstance(val, (int, long, float)) and not isinstance(val, bool):
            val = str(val)
        result_entry[key[2:]] = val
        del result_entry[key]
    return result_entry
