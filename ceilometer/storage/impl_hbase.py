#
# Copyright 2012, 2013 Dell Inc.
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
import json
import operator
import os
import re
import six
import six.moves.urllib.parse as urlparse
import time

import bson.json_util
import happybase

from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer.openstack.common import network_utils
from ceilometer.openstack.common import timeutils
from ceilometer.storage import base
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

DTYPE_NAMES = {'none': 0, 'string': 1, 'integer': 2, 'float': 3,
               'datetime': 4}
OP_SIGN = {'eq': '=', 'lt': '<', 'le': '<=', 'ne': '!=', 'gt': '>',
           'ge': '>='}


class Connection(base.Connection):
    """Put the data into a HBase database

    Collections:

    - meter (describes sample actually)
      - row-key: consists of reversed timestamp, meter and an md5 of
                 user+resource+project for purposes of uniqueness
      - Column Families:
          f: contains the following qualifiers:
               -counter_name : <name of counter>
               -counter_type : <type of counter>
               -counter_unit : <unit of counter>
               -counter_volume : <volume of counter>
               -message: <raw incoming data>
               -message_id: <id of message>
               -message_signature: <signature of message>
               -resource_metadata: raw metadata for corresponding resource
                of the meter
               -project_id: <id of project>
               -resource_id: <id of resource>
               -user_id: <id of user>
               -recorded_at: <datetime when sample has been recorded (utc.now)>
               -flattened metadata with prefix r_metadata. e.g.
                f:r_metadata.display_name or f:r_metadata.tag
               -rts: <reversed timestamp of entry>
               -timestamp: <meter's timestamp (came from message)>
               -source for meter with prefix 's'

    - resource
      - row_key: uuid of resource
      - Column Families:
          f: contains the following qualifiers:
               -resource_metadata: raw metadata for corresponding resource
               -project_id: <id of project>
               -resource_id: <id of resource>
               -user_id: <id of user>
               -flattened metadata with prefix r_metadata. e.g.
                f:r_metadata.display_name or f:r_metadata.tag
               -sources for all corresponding meters with prefix 's'
               -all meters for this resource in format
                "%s+%s+%s!%s!%s" % (rts, source, counter_name, counter_type,
                 counter_unit)

    - alarm
      - row_key: uuid of alarm
      - Column Families:
          f: contains the raw incoming alarm data

    - alarm_h
      - row_key: uuid of alarm + "_" + reversed timestamp
      - Column Families:
          f: raw incoming alarm_history data. Timestamp becomes now()
             if not determined

    - events
      - row_key: timestamp of event's generation + uuid of event
                 in format: "%s+%s" % (ts, Event.message_id)
      -Column Families:
          f: contains the following qualifiers:
              -event_type: description of event's type
              -timestamp: time stamp of event generation
              -all traits for this event in format
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
    ALARM_TABLE = "alarm"
    ALARM_HISTORY_TABLE = "alarm_h"
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
                    Connection._memory_instance = MConnectionPool()
                self.conn_pool = Connection._memory_instance
        else:
            self.conn_pool = self._get_connection_pool(opts)

    def upgrade(self):
        with self.conn_pool.connection() as conn:
            conn.create_table(self.RESOURCE_TABLE, {'f': dict(max_versions=1)})
            conn.create_table(self.METER_TABLE, {'f': dict(max_versions=1)})
            conn.create_table(self.ALARM_TABLE, {'f': dict()})
            conn.create_table(self.ALARM_HISTORY_TABLE, {'f': dict()})
            conn.create_table(self.EVENT_TABLE, {'f': dict(max_versions=1)})

    def clear(self):
        LOG.debug(_('Dropping HBase schema...'))
        with self.conn_pool.connection() as conn:
            for table in [self.RESOURCE_TABLE,
                          self.METER_TABLE,
                          self.ALARM_TABLE,
                          self.ALARM_HISTORY_TABLE,
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
        rts = timestamp(ts)
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
            resource_table = conn.table(self.RESOURCE_TABLE)
            meter_table = conn.table(self.METER_TABLE)

            resource_metadata = data.get('resource_metadata', {})
            # Determine the name of new meter
            rts = timestamp(data['timestamp'])
            new_meter = _format_meter_reference(
                data['counter_name'], data['counter_type'],
                data['counter_unit'], rts, data['source'])

            #TODO(nprivalova): try not to store resource_id
            resource = serialize_entry(**{
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

            #TODO(nprivalova): improve uniqueness
            # Rowkey consists of reversed timestamp, meter and an md5 of
            # user+resource+project for purposes of uniqueness
            m = hashlib.md5()
            m.update("%s%s%s" % (data['user_id'], data['resource_id'],
                                 data['project_id']))
            row = "%s_%d_%s" % (data['counter_name'], rts, m.hexdigest())
            record = serialize_entry(data, **{'source': data['source'],
                                              'rts': rts,
                                              'message': data,
                                              'recorded_at': timeutils.utcnow(
                                              )})
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

        q = make_query(metaquery=metaquery, user_id=user, project_id=project,
                       resource_id=resource, source=source)
        q = make_meter_query_for_resource(start_timestamp, start_timestamp_op,
                                          end_timestamp, end_timestamp_op,
                                          source, q)
        with self.conn_pool.connection() as conn:
            resource_table = conn.table(self.RESOURCE_TABLE)
            LOG.debug(_("Query Resource table: %s") % q)
            for resource_id, data in resource_table.scan(filter=q):
                f_res, sources, meters, md = deserialize_entry(data)
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
                    f_res, _s, _m, md = deserialize_entry(row)
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
            q = make_query(metaquery=metaquery, user_id=user,
                           project_id=project, resource_id=resource,
                           source=source)
            LOG.debug(_("Query Resource table: %s") % q)

            gen = resource_table.scan(filter=q)
            # We need result set to be sure that user doesn't receive several
            # same meters. Please see bug
            # https://bugs.launchpad.net/ceilometer/+bug/1301371
            result = set()
            for ignored, data in gen:
                flatten_result, s, meters, md = deserialize_entry(data)
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
            q, start, stop, columns = make_sample_query_from_filter(
                sample_filter, require_meter=False)
            LOG.debug(_("Query Meter Table: %s") % q)
            gen = meter_table.scan(filter=q, row_start=start, row_stop=stop,
                                   limit=limit)
            for ignored, meter in gen:
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
            q, start, stop, columns = make_sample_query_from_filter(
                sample_filter)
            # These fields are used in statistics' calculating
            columns.extend(['f:timestamp', 'f:counter_volume',
                            'f:counter_unit'])
            meters = map(deserialize_entry, list(meter for (ignored, meter) in
                         meter_table.scan(filter=q, row_start=start,
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

    def record_events(self, event_models):
        """Write the events to Hbase.

        :param event_models: a list of models.Event objects.
        """
        problem_events = []

        with self.conn_pool.connection() as conn:
            events_table = conn.table(self.EVENT_TABLE)
            for event_model in event_models:
                # Row key consists of timestamp and message_id from
                # models.Event or purposes of storage event sorted by
                # timestamp in the database.
                ts = event_model.generated
                row = "%d_%s" % (timestamp(ts, reverse=False),
                                 event_model.message_id)
                event_type = event_model.event_type
                traits = {}
                if event_model.traits:
                    for trait in event_model.traits:
                        key = "%s+%d" % (trait.name, trait.dtype)
                        traits[key] = trait.value
                record = serialize_entry(traits, event_type=event_type,
                                         timestamp=ts)
                try:
                    events_table.put(row, record)
                except Exception as ex:
                    LOG.debug(_("Failed to record event: %s") % ex)
                    problem_events.append((models.Event.UNKNOWN_PROBLEM,
                                           event_model))
        return problem_events

    def get_events(self, event_filter):
        """Return an iterable of models.Event objects.

        :param event_filter: storage.EventFilter object, consists of filters
                             for events that are stored in database.
        """
        q, start, stop = make_events_query_from_filter(event_filter)
        with self.conn_pool.connection() as conn:
            events_table = conn.table(self.EVENT_TABLE)

            gen = events_table.scan(filter=q, row_start=start, row_stop=stop)

        events = []
        for event_id, data in gen:
            traits = []
            events_dict = deserialize_entry(data)[0]
            for key, value in events_dict.items():
                if (not key.startswith('event_type')
                        and not key.startswith('timestamp')):
                    trait_name, trait_dtype = key.rsplit('+', 1)
                    traits.append(models.Trait(name=trait_name,
                                               dtype=int(trait_dtype),
                                               value=value))
            ts, mess = event_id.split('_', 1)

            events.append(models.Event(
                message_id=mess,
                event_type=events_dict['event_type'],
                generated=events_dict['timestamp'],
                traits=sorted(traits, key=(lambda item:
                                           getattr(item, 'dtype')))
            ))
        return events

    def get_event_types(self):
        """Return all event types as an iterable of strings."""
        with self.conn_pool.connection() as conn:
            events_table = conn.table(self.EVENT_TABLE)
            gen = events_table.scan()

        event_types = set()
        for event_id, data in gen:
            events_dict = deserialize_entry(data)[0]
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

        q = make_query(event_type=event_type)
        trait_types = set()
        with self.conn_pool.connection() as conn:
            events_table = conn.table(self.EVENT_TABLE)
            gen = events_table.scan(filter=q)
        for event_id, data in gen:
            events_dict = deserialize_entry(data)[0]
            for key, value in events_dict.items():
                if (not key.startswith('event_type') and
                        not key.startswith('timestamp')):
                    name, tt_number = key.rsplit('+', 1)
                    if name not in trait_types:
                        # Here we check that our method return only unique
                        # trait types, for ex. if it is found the same trait
                        # types in different events with equal event_type,
                        # method will return only one trait type. It is
                        # proposed that certain trait name could have only one
                        # trait type.
                        trait_types.add(name)
                        data_type = models.Trait.type_names[int(tt_number)]
                        yield {'name': name, 'data_type': data_type}

    def get_traits(self, event_type, trait_type=None):
        """Return all trait instances associated with an event_type. If
        trait_type is specified, only return instances of that trait type.

        :param event_type: the type of the Event to filter by
        :param trait_type: the name of the Trait to filter by
        """
        q = make_query(event_type=event_type, trait_type=trait_type)
        traits = []
        with self.conn_pool.connection() as conn:
            events_table = conn.table(self.EVENT_TABLE)
            gen = events_table.scan(filter=q)
        for event_id, data in gen:
            events_dict = deserialize_entry(data)[0]
            for key, value in events_dict.items():
                if (not key.startswith('event_type') and
                        not key.startswith('timestamp')):
                    name, tt_number = key.rsplit('+', 1)
                    traits.append(models.Trait(name=name,
                                  dtype=int(tt_number), value=value))
        for trait in sorted(traits, key=operator.attrgetter('dtype')):
            yield trait


def _QualifierFilter(op, qualifier):
    return "QualifierFilter (%s, 'binaryprefix:m_%s')" % (op, qualifier)


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
        self._rows_with_ts = {}

    def row(self, key, columns=None):
        if key not in self._rows_with_ts:
            return {}
        res = copy.copy(sorted(six.iteritems(
            self._rows_with_ts.get(key)))[-1][1])
        if columns:
            keys = res.keys()
            for key in keys:
                if key not in columns:
                    res.pop(key)
        return res

    def rows(self, keys):
        return ((k, self.row(k)) for k in keys)

    def put(self, key, data, ts=None):
        # Note: Now we use 'timestamped' but only for one Resource table.
        # That's why we may put ts='0' in case when ts is None. If it is
        # needed to use 2 types of put in one table ts=0 cannot be used.
        if ts is None:
            ts = "0"
        if key not in self._rows_with_ts:
            self._rows_with_ts[key] = {ts: data}
        else:
            if ts in self._rows_with_ts[key]:
                self._rows_with_ts[key][ts].update(data)
            else:
                self._rows_with_ts[key].update({ts: data})

    def delete(self, key):
        del self._rows_with_ts[key]

    def _get_latest_dict(self, row):
        # The idea here is to return latest versions of columns.
        # In _rows_with_ts we store {row: {ts_1: {data}, ts_2: {data}}}.
        # res will contain a list of tuples [(ts_1, {data}), (ts_2, {data})]
        # sorted by ts, i.e. in this list ts_2 is the most latest.
        # To get result as HBase provides we should iterate in reverse order
        # and get from "latest" data only key-values that are not in newer data
        data = {}
        for i in sorted(six.iteritems(self._rows_with_ts[row])):
            data.update(i[1])
        return data

    def scan(self, filter=None, columns=None, row_start=None, row_stop=None,
             limit=None):
        columns = columns or []
        sorted_keys = sorted(self._rows_with_ts)
        # copy data between row_start and row_stop into a dict
        rows = {}
        for row in sorted_keys:
            if row_start and row < row_start:
                continue
            if row_stop and row > row_stop:
                break
            rows[row] = self._get_latest_dict(row)

        if columns:
            ret = {}
            for row, data in six.iteritems(rows):
                for key in data:
                    if key in columns:
                        ret[row] = data
            rows = ret
        if filter:
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
        for k in sorted(rows)[:limit]:
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

    @staticmethod
    def ColumnPrefixFilter(args, rows):
        """This is filter for testing "in-memory HBase".

        This method is called from scan() when 'ColumnPrefixFilter' is found
        in the 'filter' argument
        :param args is list of filter arguments, contain prefix of column
        :param rows is dict of row prefixes for filtering
        """
        value = args[0]
        column = 'f:' + value
        r = {}
        for row, data in rows.items():
            column_dict = {}
            for key in data:
                if key.startswith(column):
                    column_dict[key] = data[key]
            r[row] = column_dict
        return r

    @staticmethod
    def RowFilter(args, rows):
        """This is filter for testing "in-memory HBase".

        This method is called from scan() when 'RowFilter'
        is found in the 'filter' argument
        :param args is list of filter arguments, it contains operator and
        sought string
        :param rows is dict of rows which are filtered
        """
        op = args[0]
        value = args[1]
        if value.startswith('regexstring:'):
            value = value[len('regexstring:'):]
        r = {}
        for row, data in rows.items():
            try:
                g = re.search(value, row).group()
                if op == '=':
                    if g == row:
                        r[row] = data
                else:
                    raise NotImplementedError("In-memory "
                                              "RowFilter doesn't support "
                                              "the %s operation yet" % op)
            except AttributeError:
                pass
        return r

    @staticmethod
    def QualifierFilter(args, rows):
        """This method is called from scan() when 'QualifierFilter'
        is found in the 'filter' argument
        """
        op = args[0]
        value = args[1]
        if value.startswith('binaryprefix:'):
            value = value[len('binaryprefix:'):]
        column = 'f:' + value
        r = {}
        for row in rows:
            data = rows[row]
            r_data = {}
            for key in data:
                if (op == '=' and key.startswith(column)) or \
                        (op == '>=' and key >= column) or \
                        (op == '<=' and key <= column):
                    r_data[key] = data[key]
                else:
                    raise NotImplementedError("In-memory QualifierFilter "
                                              "doesn't support the %s "
                                              "operation yet" % op)
            if r_data:
                r[row] = r_data
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

    def create_table(self, n, families=None):
        families = families or {}
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
def timestamp(dt, reverse=True):
    """Timestamp is count of milliseconds since start of epoch.

    If reverse=True then timestamp will be reversed. Such a technique is used
    in HBase rowkey design when period queries are required. Because of the
    fact that rows are sorted lexicographically it's possible to vary whether
    the 'oldest' entries will be on top of the table or it should be the newest
    ones (reversed timestamp case).

    :param: dt: datetime which is translated to timestamp
    :param: reverse: a boolean parameter for reverse or straight count of
    timestamp in milliseconds
    :return count or reversed count of milliseconds since start of epoch
    """
    epoch = datetime.datetime(1970, 1, 1)
    td = dt - epoch
    ts = td.microseconds + td.seconds * 1000000 + td.days * 86400000000
    return 0x7fffffffffffffff - ts if reverse else ts


def make_events_query_from_filter(event_filter):
    """Return start and stop row for filtering and a query which based on the
    selected parameter.

    :param event_filter: storage.EventFilter object.
    """
    q = []
    res_q = None
    start = "%s" % (timestamp(event_filter.start_time, reverse=False)
                    if event_filter.start_time else "")
    stop = "%s" % (timestamp(event_filter.end_time, reverse=False)
                   if event_filter.end_time else "")
    if event_filter.event_type:
        q.append("SingleColumnValueFilter ('f', 'event_type', = , "
                 "'binary:%s')" % dump(event_filter.event_type))
    if event_filter.message_id:
        q.append("RowFilter ( = , 'regexstring:\d*_%s')" %
                 event_filter.message_id)
    if len(q):
        res_q = " AND ".join(q)

    if event_filter.traits_filter:
        for trait_filter in event_filter.traits_filter:
            q_trait = make_query(trait_query=True, **trait_filter)
            if q_trait:
                if res_q:
                    res_q += " AND " + q_trait
                else:
                    res_q = q_trait
    return res_q, start, stop


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

    rts_start = str(timestamp(start) + 1) if start else ""
    rts_end = str(timestamp(end) + 1) if end else ""

    # By default, we are using ge for lower bound and lt for upper bound
    if start_op == 'gt':
        rts_start = str(long(rts_start) - 2)
    if end_op == 'le':
        rts_end = str(long(rts_end) - 1)

    return rts_start, rts_end


def make_query(metaquery=None, trait_query=None, **kwargs):
    """Return a filter query string based on the selected parameters.

    :param metaquery: optional metaquery dict
    :param trait_query: optional boolean, for trait_query from kwargs
    :param kwargs: key-value pairs to filter on. Key should be a real
     column name in db
    """
    q = []
    res_q = None

    # Query for traits differs from others. It is constructed with
    # SingleColumnValueFilter with the possibility to choose comparision
    # operator
    if trait_query:
        trait_name = kwargs.pop('key')
        op = kwargs.pop('op', 'eq')
        for k, v in kwargs.items():
            if v is not None:
                res_q = ("SingleColumnValueFilter "
                         "('f', '%s+%d', %s, 'binary:%s', true, true)" %
                         (trait_name, DTYPE_NAMES[k], OP_SIGN[op],
                          dump(v)))
        return res_q

    # Note: we use extended constructor for SingleColumnValueFilter here.
    # It is explicitly specified that entry should not be returned if CF is not
    # found in table.
    for key, value in sorted(kwargs.items()):
        if value is not None:
            if key == 'source':
                q.append("SingleColumnValueFilter "
                         "('f', 's_%s', =, 'binary:%s', true, true)" %
                         (value, dump('1')))
            elif key == 'trait_type':
                q.append("ColumnPrefixFilter('%s')" % value)
            else:
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


def _get_meter_columns(metaquery, **kwargs):
    """Return a list of required columns in meter table to be scanned .

    :param metaquery: optional metaquery dict
    :param kwargs: key-value pairs to filter on. Key should be a real
     column name in db
    """
    columns = ['f:message', 'f:recorded_at']
    columns.extend(["f:%s" % k for k, v in kwargs.items() if v])
    if metaquery:
        columns.extend(["f:r_%s" % k for k, v in metaquery.items() if v])
    return columns


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

    kwargs = dict(user_id=sample_filter.user,
                  project_id=sample_filter.project,
                  counter_name=meter,
                  resource_id=sample_filter.resource,
                  source=sample_filter.source,
                  message_id=sample_filter.message_id)

    q = make_query(metaquery=sample_filter.metaquery, **kwargs)

    if q:
        ts_query = (" AND " + ts_query) if ts_query else ""
        res_q = q + ts_query if ts_query else q
    else:
        res_q = ts_query if ts_query else None
    columns = _get_meter_columns(metaquery=sample_filter.metaquery, **kwargs)
    return res_q, start_row, end_row, columns


def make_meter_query_for_resource(start_timestamp, start_timestamp_op,
                                  end_timestamp, end_timestamp_op, source,
                                  query=None):
    """This method is used when Resource table should be filtered by meters.
       In this method we are looking into all qualifiers with m_ prefix.

    :param start_timestamp: meter's timestamp start range.
    :param start_timestamp_op: meter's start time operator, like ge, gt.
    :param end_timestamp: meter's timestamp end range.
    :param end_timestamp_op: meter's end time operator, like lt, le.
    :param source: source filter.
    :param query: a query string to concatenate with.
    """
    start_rts, end_rts = get_start_end_rts(start_timestamp,
                                           start_timestamp_op,
                                           end_timestamp, end_timestamp_op)
    mq = []

    if start_rts:
        filter_value = start_rts + '+' + source if source else start_rts
        mq.append(_QualifierFilter("<=", filter_value))

    if end_rts:
        filter_value = end_rts + '+' + source if source else end_rts
        mq.append(_QualifierFilter(">=", filter_value))

    if mq:
        meter_q = " AND ".join(mq)
        # If there is a filtering on time_range we need to point that
        # qualifiers should start with m_. Overwise in case e.g.
        # QualifierFilter (>=, 'binaryprefix:m_9222030811134775808')
        # qualifier 's_test' satisfies the filter and will be returned.
        meter_q = _QualifierFilter("=", '') + " AND " + meter_q
        query = meter_q if not query else query + " AND " + meter_q
    return query


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


def _format_meter_reference(c_name, c_type, c_unit, rts, source):
    """Format reference to meter data.
    """
    return "%s+%s+%s!%s!%s" % (rts, source, c_name, c_type, c_unit)


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
        elif k.startswith('f:r_metadata.'):
            metadata_flattened[k[len('f:r_metadata.'):]] = load(v)
        elif k.startswith("f:m_"):
            meter = (k[4:], load(v))
            meters.append(meter)
        else:
            flatten_result[k[2:]] = load(v)
    if get_raw_meta:
        metadata = flatten_result.get('resource_metadata', {})
    else:
        metadata = metadata_flattened

    return flatten_result, sources, meters, metadata


def serialize_entry(data=None, **kwargs):
    """Return a dict that is ready to be stored to HBase

    :param data: dict to be serialized
    :param kwargs: additional args
    """
    data = data or {}
    entry_dict = copy.copy(data)
    entry_dict.update(**kwargs)

    result = {}
    for k, v in entry_dict.items():
        if k == 'source':
            # user, project and resource tables may contain several sources.
            # Besides, resource table may contain several meters.
            # To make insertion safe we need to store all meters and sources in
            # a separate cell. For this purpose s_ and m_ prefixes are
            # introduced.
                result['f:s_%s' % v] = dump('1')
        elif k == 'meter':
            for meter, ts in v.items():
                result['f:m_%s' % meter] = dump(ts)
        elif k == 'resource_metadata':
            # keep raw metadata as well as flattened to provide
            # capability with API v2. It will be flattened in another
            # way on API level. But we need flattened too for quick filtering.
            flattened_meta = dump_metadata(v)
            for k, m in flattened_meta.items():
                result['f:r_metadata.' + k] = dump(m)
            result['f:resource_metadata'] = dump(v)
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
