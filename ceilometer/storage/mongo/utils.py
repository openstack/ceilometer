#
# Copyright Ericsson AB 2013. All rights reserved
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
"""Common functions for MongoDB backend
"""

import datetime
import time
import weakref

from oslo_log import log
from oslo_utils import netutils
import pymongo
import pymongo.errors
import six
from six.moves.urllib import parse

from ceilometer.i18n import _

ERROR_INDEX_WITH_DIFFERENT_SPEC_ALREADY_EXISTS = 86

LOG = log.getLogger(__name__)

MINIMUM_COMPATIBLE_MONGODB_VERSION = [2, 4]
COMPLETE_AGGREGATE_COMPATIBLE_VERSION = [2, 6]

FINALIZE_FLOAT_LAMBDA = lambda result, param=None: float(result)
FINALIZE_INT_LAMBDA = lambda result, param=None: int(result)
CARDINALITY_VALIDATION = (lambda name, param: param in ['resource_id',
                                                        'user_id',
                                                        'project_id',
                                                        'source'])


def make_timestamp_range(start, end,
                         start_timestamp_op=None, end_timestamp_op=None):

    """Create the query document to find timestamps within that range.

    This is done by given two possible datetimes and their operations.
    By default, using $gte for the lower bound and $lt for the upper bound.
    """
    ts_range = {}

    if start:
        if start_timestamp_op == 'gt':
            start_timestamp_op = '$gt'
        else:
            start_timestamp_op = '$gte'
        ts_range[start_timestamp_op] = start

    if end:
        if end_timestamp_op == 'le':
            end_timestamp_op = '$lte'
        else:
            end_timestamp_op = '$lt'
        ts_range[end_timestamp_op] = end
    return ts_range


def make_query_from_filter(sample_filter, require_meter=True):
    """Return a query dictionary based on the settings in the filter.

    :param sample_filter: SampleFilter instance
    :param require_meter: If true and the filter does not have a meter,
                          raise an error.
    """
    q = {}

    if sample_filter.user:
        q['user_id'] = sample_filter.user
    if sample_filter.project:
        q['project_id'] = sample_filter.project

    if sample_filter.meter:
        q['counter_name'] = sample_filter.meter
    elif require_meter:
        raise RuntimeError('Missing required meter specifier')

    ts_range = make_timestamp_range(sample_filter.start_timestamp,
                                    sample_filter.end_timestamp,
                                    sample_filter.start_timestamp_op,
                                    sample_filter.end_timestamp_op)

    if ts_range:
        q['timestamp'] = ts_range

    if sample_filter.resource:
        q['resource_id'] = sample_filter.resource
    if sample_filter.source:
        q['source'] = sample_filter.source
    if sample_filter.message_id:
        q['message_id'] = sample_filter.message_id

    # so the samples call metadata resource_metadata, so we convert
    # to that.
    q.update(dict(
        ('resource_%s' % k, v) for (k, v) in six.iteritems(
            improve_keys(sample_filter.metaquery, metaquery=True))))
    return q


def quote_key(key, reverse=False):
    """Prepare key for storage data in MongoDB.

    :param key: key that should be quoted
    :param reverse: boolean, True --- if we need a reverse order of the keys
                    parts
    :return: iter of quoted part of the key
    """
    r = -1 if reverse else 1

    for k in key.split('.')[::r]:
        if k.startswith('$'):
            k = parse.quote(k)
        yield k


def improve_keys(data, metaquery=False):
    """Improves keys in dict if they contained '.' or started with '$'.

    :param data: is a dictionary where keys need to be checked and improved
    :param metaquery: boolean, if True dots are not escaped from the keys
    :return: improved dictionary if keys contained dots or started with '$':
            {'a.b': 'v'} -> {'a': {'b': 'v'}}
            {'$ab': 'v'} -> {'%24ab': 'v'}
    """
    if not isinstance(data, dict):
        return data

    if metaquery:
        for key in six.iterkeys(data):
            if '.$' in key:
                key_list = []
                for k in quote_key(key):
                    key_list.append(k)
                new_key = '.'.join(key_list)
                data[new_key] = data.pop(key)
    else:
        for key, value in data.items():
            if isinstance(value, dict):
                improve_keys(value)
            if '.' in key:
                new_dict = {}
                for k in quote_key(key, reverse=True):
                    new = {}
                    new[k] = new_dict if new_dict else data.pop(key)
                    new_dict = new
                data.update(new_dict)
            else:
                if key.startswith('$'):
                    new_key = parse.quote(key)
                    data[new_key] = data.pop(key)
    return data


def unquote_keys(data):
    """Restores initial view of 'quoted' keys in dictionary data

    :param data: is a dictionary
    :return: data with restored keys if they were 'quoted'.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                unquote_keys(value)
            if key.startswith('%24'):
                k = parse.unquote(key)
                data[k] = data.pop(key)
    return data


class ConnectionPool(object):

    def __init__(self):
        self._pool = {}

    def connect(self, conf, url):
        connection_options = pymongo.uri_parser.parse_uri(url)
        del connection_options['database']
        del connection_options['username']
        del connection_options['password']
        del connection_options['collection']
        pool_key = tuple(connection_options)

        if pool_key in self._pool:
            client = self._pool.get(pool_key)()
            if client:
                return client
        splitted_url = netutils.urlsplit(url)
        log_data = {'db': splitted_url.scheme,
                    'nodelist': connection_options['nodelist']}
        LOG.info('Connecting to %(db)s on %(nodelist)s' % log_data)
        client = self._mongo_connect(conf, url)
        self._pool[pool_key] = weakref.ref(client)
        return client

    @staticmethod
    def _mongo_connect(conf, url):
        try:
            return MongoProxy(conf, pymongo.MongoClient(url))
        except pymongo.errors.ConnectionFailure as e:
            LOG.warning(_('Unable to connect to the database server: '
                        '%(errmsg)s.') % {'errmsg': e})
            raise


class QueryTransformer(object):

    operators = {"<": "$lt",
                 ">": "$gt",
                 "<=": "$lte",
                 "=<": "$lte",
                 ">=": "$gte",
                 "=>": "$gte",
                 "!=": "$ne",
                 "in": "$in",
                 "=~": "$regex"}

    complex_operators = {"or": "$or",
                         "and": "$and"}

    ordering_functions = {"asc": pymongo.ASCENDING,
                          "desc": pymongo.DESCENDING}

    def transform_orderby(self, orderby):
        orderby_filter = []

        for field in orderby:
            field_name = list(field.keys())[0]
            ordering = self.ordering_functions[list(field.values())[0]]
            orderby_filter.append((field_name, ordering))
        return orderby_filter

    @staticmethod
    def _move_negation_to_leaf(condition):
        """Moves every not operator to the leafs.

        Moving is going by applying the De Morgan rules and annihilating
        double negations.
        """
        def _apply_de_morgan(tree, negated_subtree, negated_op):
            if negated_op == "and":
                new_op = "or"
            else:
                new_op = "and"

            tree[new_op] = [{"not": child}
                            for child in negated_subtree[negated_op]]
            del tree["not"]

        def transform(subtree):
            op = list(subtree.keys())[0]
            if op in ["and", "or"]:
                [transform(child) for child in subtree[op]]
            elif op == "not":
                negated_tree = subtree[op]
                negated_op = list(negated_tree.keys())[0]
                if negated_op == "and":
                    _apply_de_morgan(subtree, negated_tree, negated_op)
                    transform(subtree)
                elif negated_op == "or":
                    _apply_de_morgan(subtree, negated_tree, negated_op)
                    transform(subtree)
                elif negated_op == "not":
                    # two consecutive not annihilates themselves
                    value = list(negated_tree.values())[0]
                    new_op = list(value.keys())[0]
                    subtree[new_op] = negated_tree[negated_op][new_op]
                    del subtree["not"]
                    transform(subtree)

        transform(condition)

    def transform_filter(self, condition):
        # in Mongo not operator can only be applied to
        # simple expressions so we have to move every
        # not operator to the leafs of the expression tree
        self._move_negation_to_leaf(condition)
        return self._process_json_tree(condition)

    def _handle_complex_op(self, complex_op, nodes):
        element_list = []
        for node in nodes:
            element = self._process_json_tree(node)
            element_list.append(element)
        complex_operator = self.complex_operators[complex_op]
        op = {complex_operator: element_list}
        return op

    def _handle_not_op(self, negated_tree):
        # assumes that not is moved to the leaf already
        # so we are next to a leaf
        negated_op = list(negated_tree.keys())[0]
        negated_field = list(negated_tree[negated_op].keys())[0]
        value = negated_tree[negated_op][negated_field]
        if negated_op == "=":
            return {negated_field: {"$ne": value}}
        elif negated_op == "!=":
            return {negated_field: value}
        else:
            return {negated_field: {"$not":
                                    {self.operators[negated_op]: value}}}

    def _handle_simple_op(self, simple_op, nodes):
        field_name = list(nodes.keys())[0]
        field_value = list(nodes.values())[0]

        # no operator for equal in Mongo
        if simple_op == "=":
            op = {field_name: field_value}
            return op

        operator = self.operators[simple_op]
        op = {field_name: {operator: field_value}}
        return op

    def _process_json_tree(self, condition_tree):
        operator_node = list(condition_tree.keys())[0]
        nodes = list(condition_tree.values())[0]

        if operator_node in self.complex_operators:
            return self._handle_complex_op(operator_node, nodes)

        if operator_node == "not":
            negated_tree = condition_tree[operator_node]
            return self._handle_not_op(negated_tree)

        return self._handle_simple_op(operator_node, nodes)


def safe_mongo_call(call):
    def closure(self, *args, **kwargs):
        # NOTE(idegtiarov) options max_retries and retry_interval have been
        # registered in storage.__init__ in oslo_db.options.set_defaults
        # default values for both options are 10.
        max_retries = self.conf.database.max_retries
        retry_interval = self.conf.database.retry_interval
        attempts = 0
        while True:
            try:
                return call(self, *args, **kwargs)
            except pymongo.errors.AutoReconnect as err:
                if 0 <= max_retries <= attempts:
                    LOG.error('Unable to reconnect to the primary mongodb '
                              'after %(retries)d retries. Giving up.' %
                              {'retries': max_retries})
                    raise
                LOG.warning(_('Unable to reconnect to the primary '
                              'mongodb: %(errmsg)s. Trying again in '
                              '%(retry_interval)d seconds.') %
                            {'errmsg': err, 'retry_interval': retry_interval})
                attempts += 1
                time.sleep(retry_interval)
    return closure


class MongoConn(object):
    def __init__(self, conf, method):
        self.conf = conf
        self.method = method

    @safe_mongo_call
    def __call__(self, *args, **kwargs):
        return self.method(*args, **kwargs)

MONGO_METHODS = set([typ for typ in dir(pymongo.collection.Collection)
                     if not typ.startswith('_')])
MONGO_METHODS.update(set([typ for typ in dir(pymongo.MongoClient)
                          if not typ.startswith('_')]))
MONGO_METHODS.update(set([typ for typ in dir(pymongo)
                          if not typ.startswith('_')]))


class MongoProxy(object):
    def __init__(self, conf, conn):
        self.conn = conn
        self.conf = conf

    def __getitem__(self, item):
        """Create and return proxy around the method in the connection.

        :param item: name of the connection
        """
        return MongoProxy(self.conf, self.conn[item])

    def find(self, *args, **kwargs):
        # We need this modifying method to return a CursorProxy object so that
        # we can handle the Cursor next function to catch the AutoReconnect
        # exception.
        return CursorProxy(self.conf, self.conn.find(*args, **kwargs))

    def create_index(self, keys, name=None, *args, **kwargs):
        try:
            self.conn.create_index(keys, name=name, *args, **kwargs)
        except pymongo.errors.OperationFailure as e:
            if e.code is ERROR_INDEX_WITH_DIFFERENT_SPEC_ALREADY_EXISTS:
                LOG.info("Index %s will be recreate.", name)
                self._recreate_index(keys, name, *args, **kwargs)

    @safe_mongo_call
    def _recreate_index(self, keys, name, *args, **kwargs):
        self.conn.drop_index(name)
        self.conn.create_index(keys, name=name, *args, **kwargs)

    def __getattr__(self, item):
        """Wrap MongoDB connection.

        If item is the name of an executable method, for example find or
        insert, wrap this method in the MongoConn.
        Else wrap getting attribute with MongoProxy.
        """
        if item in ("conf",):
            return super(MongoProxy, self).__getattr__(item)
        elif item in ('name', 'database'):
            return getattr(self.conn, item)
        elif item in MONGO_METHODS:
            return MongoConn(self.conf, getattr(self.conn, item))
        return MongoProxy(self.conf, getattr(self.conn, item))

    def __call__(self, *args, **kwargs):
        return self.conn(*args, **kwargs)


class CursorProxy(pymongo.cursor.Cursor):
    def __init__(self, conf, cursor):
        self.cursor = cursor
        self.conf = conf

    def __getitem__(self, item):
        return self.cursor[item]

    @safe_mongo_call
    def next(self):
        """Wrap Cursor next method.

        This method will be executed before each Cursor next method call.
        """
        try:
            save_cursor = self.cursor.clone()
            return self.cursor.next()
        except pymongo.errors.AutoReconnect:
            self.cursor = save_cursor
            raise

    def __getattr__(self, item):
        return getattr(self.cursor, item)


class AggregationFields(object):
    def __init__(self, version,
                 group,
                 project,
                 finalize=None,
                 parametrized=False,
                 validate=None):
        self._finalize = finalize or FINALIZE_FLOAT_LAMBDA
        self.group = lambda *args: group(*args) if parametrized else group
        self.project = (lambda *args: project(*args)
                        if parametrized else project)
        self.version = version
        self.validate = validate or (lambda name, param: True)

    def finalize(self, name, data, param=None):
        field = ("%s" % name) + ("/%s" % param if param else "")
        return {field: (self._finalize(data.get(field))
                        if self._finalize else data.get(field))}


class Aggregation(object):
    def __init__(self, name, aggregation_fields):
        self.name = name
        aggregation_fields = (aggregation_fields
                              if isinstance(aggregation_fields, list)
                              else [aggregation_fields])
        self.aggregation_fields = sorted(aggregation_fields,
                                         key=lambda af: getattr(af, "version"),
                                         reverse=True)

    def _get_compatible_aggregation_field(self, version_array):
        if version_array:
            version_array = version_array[0:2]
        else:
            version_array = MINIMUM_COMPATIBLE_MONGODB_VERSION
        for aggregation_field in self.aggregation_fields:
            if version_array >= aggregation_field.version:
                return aggregation_field

    def group(self, param=None, version_array=None):
        af = self._get_compatible_aggregation_field(version_array)
        return af.group(param)

    def project(self, param=None, version_array=None):
        af = self._get_compatible_aggregation_field(version_array)
        return af.project(param)

    def finalize(self, data, param=None, version_array=None):
        af = self._get_compatible_aggregation_field(version_array)
        return af.finalize(self.name, data, param)

    def validate(self, param=None, version_array=None):
        af = self._get_compatible_aggregation_field(version_array)
        return af.validate(self.name, param)

SUM_AGGREGATION = Aggregation(
    "sum", AggregationFields(MINIMUM_COMPATIBLE_MONGODB_VERSION,
                             {"sum": {"$sum": "$counter_volume"}},
                             {"sum": "$sum"},
                             ))
AVG_AGGREGATION = Aggregation(
    "avg", AggregationFields(MINIMUM_COMPATIBLE_MONGODB_VERSION,
                             {"avg": {"$avg": "$counter_volume"}},
                             {"avg": "$avg"},
                             ))
MIN_AGGREGATION = Aggregation(
    "min", AggregationFields(MINIMUM_COMPATIBLE_MONGODB_VERSION,
                             {"min": {"$min": "$counter_volume"}},
                             {"min": "$min"},
                             ))
MAX_AGGREGATION = Aggregation(
    "max", AggregationFields(MINIMUM_COMPATIBLE_MONGODB_VERSION,
                             {"max": {"$max": "$counter_volume"}},
                             {"max": "$max"},
                             ))
COUNT_AGGREGATION = Aggregation(
    "count", AggregationFields(MINIMUM_COMPATIBLE_MONGODB_VERSION,
                               {"count": {"$sum": 1}},
                               {"count": "$count"},
                               FINALIZE_INT_LAMBDA))
STDDEV_AGGREGATION = Aggregation(
    "stddev",
    AggregationFields(MINIMUM_COMPATIBLE_MONGODB_VERSION,
                      {"std_square": {
                          "$sum": {
                              "$multiply": ["$counter_volume",
                                            "$counter_volume"]
                          }},
                       "std_count": {"$sum": 1},
                       "std_sum": {"$sum": "$counter_volume"}},
                      {"stddev": {
                          "count": "$std_count",
                          "sum": "$std_sum",
                          "square_sum": "$std_square"}},
                      lambda stddev: ((stddev['square_sum']
                                       * stddev['count']
                                       - stddev["sum"] ** 2) ** 0.5
                                      / stddev['count'])))

CARDINALITY_AGGREGATION = Aggregation(
    "cardinality",
    # $cond operator available only in MongoDB 2.6+
    [AggregationFields(COMPLETE_AGGREGATE_COMPATIBLE_VERSION,
                       lambda field: ({"cardinality/%s" % field:
                                      {"$addToSet": "$%s" % field}}),
                       lambda field: {
                           "cardinality/%s" % field: {
                               "$cond": [
                                   {"$eq": ["$cardinality/%s" % field, None]},
                                   0,
                                   {"$size": "$cardinality/%s" % field}]
                           }},
                       validate=CARDINALITY_VALIDATION,
                       parametrized=True),
     AggregationFields(MINIMUM_COMPATIBLE_MONGODB_VERSION,
                       lambda field: ({"cardinality/%s" % field:
                                       {"$addToSet": "$%s" % field}}),
                       lambda field: ({"cardinality/%s" % field:
                                       "$cardinality/%s" % field}),
                       finalize=len,
                       validate=CARDINALITY_VALIDATION,
                       parametrized=True)]
)


def from_unix_timestamp(timestamp):
    if (isinstance(timestamp, six.integer_types) or
            isinstance(timestamp, float)):
        return datetime.datetime.fromtimestamp(timestamp)
    return timestamp
