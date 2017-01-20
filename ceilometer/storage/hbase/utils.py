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
"""Various HBase helpers"""
import copy
import datetime
import json

import bson.json_util
from happybase.hbase import ttypes
from oslo_log import log
import six

from ceilometer.i18n import _
from ceilometer import utils

LOG = log.getLogger(__name__)

OP_SIGN = {'eq': '=', 'lt': '<', 'le': '<=', 'ne': '!=', 'gt': '>', 'ge': '>='}
# We need this additional dictionary because we have reverted timestamp in
# row-keys for stored metrics
OP_SIGN_REV = {'eq': '=', 'lt': '>', 'le': '>=', 'ne': '!=', 'gt': '<',
               'ge': '<='}


def _QualifierFilter(op, qualifier):
    return "QualifierFilter (%s, 'binaryprefix:m_%s')" % (op, qualifier)


def timestamp(dt, reverse=True):
    """Timestamp is count of milliseconds since start of epoch.

    If reverse=True then timestamp will be reversed. Such a technique is used
    in HBase rowkey design when period queries are required. Because of the
    fact that rows are sorted lexicographically it's possible to vary whether
    the 'oldest' entries will be on top of the table or it should be the newest
    ones (reversed timestamp case).

    :param dt: datetime which is translated to timestamp
    :param reverse: a boolean parameter for reverse or straight count of
      timestamp in milliseconds
    :return: count or reversed count of milliseconds since start of epoch
    """
    epoch = datetime.datetime(1970, 1, 1)
    td = dt - epoch
    ts = td.microseconds + td.seconds * 1000000 + td.days * 86400000000
    return 0x7fffffffffffffff - ts if reverse else ts


def make_timestamp_query(func, start=None, start_op=None, end=None,
                         end_op=None, bounds_only=False, **kwargs):
    """Return a filter start and stop row for filtering and a query.

    Query is based on the fact that CF-name is 'rts'.
    :param start: Optional start timestamp
    :param start_op: Optional start timestamp operator, like gt, ge
    :param end: Optional end timestamp
    :param end_op: Optional end timestamp operator, like lt, le
    :param bounds_only: if True than query will not be returned
    :param func: a function that provide a format of row
    :param kwargs: kwargs for :param func
    """
    # We don't need to dump here because get_start_end_rts returns strings
    rts_start, rts_end = get_start_end_rts(start, end)
    start_row, end_row = func(rts_start, rts_end, **kwargs)

    if bounds_only:
        return start_row, end_row

    q = []
    start_op = start_op or 'ge'
    end_op = end_op or 'lt'
    if rts_start:
        q.append("SingleColumnValueFilter ('f', 'rts', %s, 'binary:%s')" %
                 (OP_SIGN_REV[start_op], rts_start))
    if rts_end:
        q.append("SingleColumnValueFilter ('f', 'rts', %s, 'binary:%s')" %
                 (OP_SIGN_REV[end_op], rts_end))

    res_q = None
    if len(q):
        res_q = " AND ".join(q)

    return start_row, end_row, res_q


def get_start_end_rts(start, end):

    rts_start = str(timestamp(start)) if start else ""
    rts_end = str(timestamp(end)) if end else ""
    return rts_start, rts_end


def make_query(metaquery=None, **kwargs):
    """Return a filter query string based on the selected parameters.

    :param metaquery: optional metaquery dict
    :param kwargs: key-value pairs to filter on. Key should be a real
      column name in db
    """
    q = []
    res_q = None

    # Note: we use extended constructor for SingleColumnValueFilter here.
    # It is explicitly specified that entry should not be returned if CF is not
    # found in table.
    for key, value in sorted(kwargs.items()):
        if value is not None:
            if key == 'source':
                q.append("SingleColumnValueFilter "
                         "('f', 's_%s', =, 'binary:%s', true, true)" %
                         (value, dump('1')))
            else:
                q.append("SingleColumnValueFilter "
                         "('f', '%s', =, 'binary:%s', true, true)" %
                         (quote(key), dump(value)))
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


def get_meter_columns(metaquery=None, need_timestamp=False, **kwargs):
    """Return a list of required columns in meter table to be scanned.

    SingleColumnFilter has 'columns' filter that should be used to determine
    what columns we are interested in. But if we want to use 'filter' and
    'columns' together we have to include columns we are filtering by
    to columns list.

    Please see an example: If we make scan with filter
    "SingleColumnValueFilter ('f', 's_test-1', =, 'binary:\"1\"')"
    and columns ['f:rts'], the output will be always empty
    because only 'rts' will be returned and filter will be applied
    to this data so 's_test-1' cannot be find.
    To make this request correct it should be fixed as follows:
    filter = "SingleColumnValueFilter ('f', 's_test-1', =, 'binary:\"1\"')",
    columns = ['f:rts','f:s_test-1']}

    :param metaquery: optional metaquery dict
    :param need_timestamp: flag, which defines the need for timestamp columns
    :param kwargs: key-value pairs to filter on. Key should be a real
      column name in db
    """
    columns = ['f:message', 'f:recorded_at']
    columns.extend("f:%s" % k for k, v in kwargs.items()
                   if v is not None)
    if metaquery:
        columns.extend("f:r_%s" % k for k, v in metaquery.items()
                       if v is not None)
    source = kwargs.get('source')
    if source:
        columns.append("f:s_%s" % source)
    if need_timestamp:
        columns.extend(['f:rts', 'f:timestamp'])
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
        make_general_rowkey_scan,
        start=sample_filter.start_timestamp,
        start_op=sample_filter.start_timestamp_op,
        end=sample_filter.end_timestamp,
        end_op=sample_filter.end_timestamp_op,
        some_id=meter)
    kwargs = dict(user_id=sample_filter.user,
                  project_id=sample_filter.project,
                  counter_name=meter,
                  resource_id=sample_filter.resource,
                  source=sample_filter.source,
                  message_id=sample_filter.message_id)

    q = make_query(metaquery=sample_filter.metaquery, **kwargs)

    if q:
        res_q = q + " AND " + ts_query if ts_query else q
    else:
        res_q = ts_query if ts_query else None

    need_timestamp = (sample_filter.start_timestamp or
                      sample_filter.end_timestamp) is not None
    columns = get_meter_columns(metaquery=sample_filter.metaquery,
                                need_timestamp=need_timestamp, **kwargs)
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
    start_rts, end_rts = get_start_end_rts(start_timestamp, end_timestamp)
    mq = []
    start_op = start_timestamp_op or 'ge'
    end_op = end_timestamp_op or 'lt'

    if start_rts:
        filter_value = (start_rts + ':' + quote(source) if source
                        else start_rts)
        mq.append(_QualifierFilter(OP_SIGN_REV[start_op], filter_value))

    if end_rts:
        filter_value = (end_rts + ':' + quote(source) if source
                        else end_rts)
        mq.append(_QualifierFilter(OP_SIGN_REV[end_op], filter_value))

    if mq:
        meter_q = " AND ".join(mq)
        # If there is a filtering on time_range we need to point that
        # qualifiers should start with m_. Otherwise in case e.g.
        # QualifierFilter (>=, 'binaryprefix:m_9222030811134775808')
        # qualifier 's_test' satisfies the filter and will be returned.
        meter_q = _QualifierFilter("=", '') + " AND " + meter_q
        query = meter_q if not query else query + " AND " + meter_q
    return query


def make_general_rowkey_scan(rts_start=None, rts_end=None, some_id=None):
    """If it's filter on some_id without start and end.

    start_row = some_id while end_row = some_id + MAX_BYTE.
    """
    if some_id is None:
        return None, None
    if not rts_start:
        # NOTE(idegtiarov): Here we could not use chr > 122 because chr >= 123
        # will be quoted and character will be turn in a composition that is
        # started with '%' (chr(37)) that lexicographically is less than chr
        # of number
        rts_start = chr(122)
    end_row = prepare_key(some_id, rts_start)
    start_row = prepare_key(some_id, rts_end)

    return start_row, end_row


def prepare_key(*args):
    """Prepares names for rows and columns with correct separator.

    :param args: strings or numbers that we want our key construct of
    :return: key with quoted args that are separated with character ":"
    """
    key_quote = []
    for key in args:
        if isinstance(key, six.integer_types):
            key = str(key)
        key_quote.append(quote(key))
    return ":".join(key_quote)


def timestamp_from_record_tuple(record):
    """Extract timestamp from HBase tuple record."""
    return record[0]['timestamp']


def resource_id_from_record_tuple(record):
    """Extract resource_id from HBase tuple record."""
    return record[0]['resource_id']


def deserialize_entry(entry, get_raw_meta=True):
    """Return a list of flatten_result, sources, meters and metadata.

    Flatten_result contains a dict of simple structures such as 'resource_id':1
    sources/meters are the lists of sources and meters correspondingly.
    metadata is metadata dict. This dict may be returned as flattened if
    get_raw_meta is False.

    :param entry: entry from HBase, without row name and timestamp
    :param get_raw_meta: If true then raw metadata will be returned,
                         if False metadata will be constructed from
                         'f:r_metadata.' fields
    """
    flatten_result = {}
    sources = []
    meters = []
    metadata_flattened = {}
    for k, v in entry.items():
        if k.startswith('f:s_'):
            sources.append(decode_unicode(k[4:]))
        elif k.startswith('f:r_metadata.'):
            qualifier = decode_unicode(k[len('f:r_metadata.'):])
            metadata_flattened[qualifier] = load(v)
        elif k.startswith("f:m_"):
            meter = ([unquote(i) for i in k[4:].split(':')], load(v))
            meters.append(meter)
        else:
            if ':' in k[2:]:
                key = tuple([unquote(i) for i in k[2:].split(':')])
            else:
                key = unquote(k[2:])
            flatten_result[key] = load(v)
    if get_raw_meta:
        metadata = flatten_result.get('resource_metadata', {})
    else:
        metadata = metadata_flattened

    return flatten_result, meters, metadata


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
            qualifier = encode_unicode('f:s_%s' % v)
            result[qualifier] = dump('1')
        elif k == 'meter':
            for meter, ts in v.items():
                qualifier = encode_unicode('f:m_%s' % meter)
                result[qualifier] = dump(ts)
        elif k == 'resource_metadata':
            # keep raw metadata as well as flattened to provide
            # capability with API v2. It will be flattened in another
            # way on API level. But we need flattened too for quick filtering.
            flattened_meta = dump_metadata(v)
            for key, m in flattened_meta.items():
                metadata_qualifier = encode_unicode('f:r_metadata.' + key)
                result[metadata_qualifier] = dump(m)
            result['f:resource_metadata'] = dump(v)
        else:
            result['f:' + quote(k, ':')] = dump(v)
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


def encode_unicode(data):
    return data.encode('utf-8') if isinstance(data, six.text_type) else data


def decode_unicode(data):
    return data.decode('utf-8') if isinstance(data, six.string_types) else data


# We don't want to have tzinfo in decoded json.This object_hook is
# overwritten json_util.object_hook for $date
def object_hook(dct):
    if "$date" in dct:
        dt = bson.json_util.object_hook(dct)
        return dt.replace(tzinfo=None)
    return bson.json_util.object_hook(dct)


def create_tables(conn, tables, column_families):
    for table in tables:
        try:
            conn.create_table(table, column_families)
        except ttypes.AlreadyExists:
            if conn.table_prefix:
                table = ("%(table_prefix)s"
                         "%(separator)s"
                         "%(table_name)s" %
                         dict(table_prefix=conn.table_prefix,
                              separator=conn.table_prefix_separator,
                              table_name=table))

            LOG.warning(_("Cannot create table %(table_name)s, "
                        "it already exists. Ignoring error")
                        % {'table_name': table})


def quote(s, *args):
    """Return quoted string even if it is unicode one.

    :param s: string that should be quoted
    :param args: any symbol we want to stay unquoted
    """
    s_en = s.encode('utf8')
    return six.moves.urllib.parse.quote(s_en, *args)


def unquote(s):
    """Return unquoted and decoded string.

    :param s: string that should be unquoted
    """
    s_de = six.moves.urllib.parse.unquote(s)
    return s_de.decode('utf8')
