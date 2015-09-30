#
# Copyright Ericsson AB 2013. All rights reserved
#
# Authors: Ildiko Vancsa <ildiko.vancsa@ericsson.com>
#          Balazs Gibizer <balazs.gibizer@ericsson.com>
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
"""Common functions for MongoDB and DB2 backends
"""

import time
import weakref

from oslo_config import cfg
from oslo_utils import netutils
import pymongo
import six
from six.moves.urllib import parse

from ceilometer.i18n import _
from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)

cfg.CONF.import_opt('max_retries', 'oslo.db.options', group="database")
cfg.CONF.import_opt('retry_interval', 'oslo.db.options', group="database")

EVENT_TRAIT_TYPES = {'none': 0, 'string': 1, 'integer': 2, 'float': 3,
                     'datetime': 4}
OP_SIGN = {'lt': '$lt', 'le': '$lte', 'ne': '$ne', 'gt': '$gt', 'ge': '$gte'}


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


def make_events_query_from_filter(event_filter):
    """Return start and stop row for filtering and a query.

    Query is based on the selected parameter.

    :param event_filter: storage.EventFilter object.
    """
    query = {}
    q_list = []
    ts_range = make_timestamp_range(event_filter.start_timestamp,
                                    event_filter.end_timestamp)
    if ts_range:
        q_list.append({'timestamp': ts_range})
    if event_filter.event_type:
        q_list.append({'event_type': event_filter.event_type})
    if event_filter.message_id:
        q_list.append({'_id': event_filter.message_id})

    if event_filter.traits_filter:
        for trait_filter in event_filter.traits_filter:
            op = trait_filter.pop('op', 'eq')
            dict_query = {}
            for k, v in six.iteritems(trait_filter):
                if v is not None:
                    # All parameters in EventFilter['traits'] are optional, so
                    # we need to check if they are in the query or no.
                    if k == 'key':
                        dict_query.setdefault('trait_name', v)
                    elif k in ['string', 'integer', 'datetime', 'float']:
                        dict_query.setdefault('trait_type',
                                              EVENT_TRAIT_TYPES[k])
                        dict_query.setdefault('trait_value',
                                              v if op == 'eq'
                                              else {OP_SIGN[op]: v})
            dict_query = {'$elemMatch': dict_query}
            q_list.append({'traits': dict_query})
    if q_list:
        query = {'$and': q_list}
    return query


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
        for key in data.iterkeys():
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

    def connect(self, url):
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
        LOG.info(_('Connecting to %(db)s on %(nodelist)s') % log_data)
        client = self._mongo_connect(url)
        self._pool[pool_key] = weakref.ref(client)
        return client

    @staticmethod
    def _mongo_connect(url):
        try:
            if cfg.CONF.database.mongodb_replica_set:
                client = MongoProxy(
                    pymongo.MongoReplicaSetClient(
                        url,
                        replicaSet=cfg.CONF.database.mongodb_replica_set))
            else:
                client = MongoProxy(pymongo.MongoClient(url))
            return client
        except pymongo.errors.ConnectionFailure as e:
            LOG.warn(_('Unable to connect to the database server: '
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
            field_name = field.keys()[0]
            ordering = self.ordering_functions[field.values()[0]]
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
            op = subtree.keys()[0]
            if op in ["and", "or"]:
                [transform(child) for child in subtree[op]]
            elif op == "not":
                negated_tree = subtree[op]
                negated_op = negated_tree.keys()[0]
                if negated_op == "and":
                    _apply_de_morgan(subtree, negated_tree, negated_op)
                    transform(subtree)
                elif negated_op == "or":
                    _apply_de_morgan(subtree, negated_tree, negated_op)
                    transform(subtree)
                elif negated_op == "not":
                    # two consecutive not annihilates themselves
                    new_op = negated_tree.values()[0].keys()[0]
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
        negated_op = negated_tree.keys()[0]
        negated_field = negated_tree[negated_op].keys()[0]
        value = negated_tree[negated_op][negated_field]
        if negated_op == "=":
            return {negated_field: {"$ne": value}}
        elif negated_op == "!=":
            return {negated_field: value}
        else:
            return {negated_field: {"$not":
                                    {self.operators[negated_op]: value}}}

    def _handle_simple_op(self, simple_op, nodes):
        field_name = nodes.keys()[0]
        field_value = nodes.values()[0]

        # no operator for equal in Mongo
        if simple_op == "=":
            op = {field_name: field_value}
            return op

        operator = self.operators[simple_op]
        op = {field_name: {operator: field_value}}
        return op

    def _process_json_tree(self, condition_tree):
        operator_node = condition_tree.keys()[0]
        nodes = condition_tree.values()[0]

        if operator_node in self.complex_operators:
            return self._handle_complex_op(operator_node, nodes)

        if operator_node == "not":
            negated_tree = condition_tree[operator_node]
            return self._handle_not_op(negated_tree)

        return self._handle_simple_op(operator_node, nodes)


def safe_mongo_call(call):
    def closure(*args, **kwargs):
        max_retries = cfg.CONF.database.max_retries
        retry_interval = cfg.CONF.database.retry_interval
        attempts = 0
        while True:
            try:
                return call(*args, **kwargs)
            except pymongo.errors.AutoReconnect as err:
                if 0 <= max_retries <= attempts:
                    LOG.error(_('Unable to reconnect to the primary mongodb '
                                'after %(retries)d retries. Giving up.') %
                              {'retries': max_retries})
                    raise
                LOG.warn(_('Unable to reconnect to the primary mongodb: '
                           '%(errmsg)s. Trying again in %(retry_interval)d '
                           'seconds.') %
                         {'errmsg': err, 'retry_interval': retry_interval})
                attempts += 1
                time.sleep(retry_interval)
    return closure


class MongoConn(object):
    def __init__(self, method):
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
    def __init__(self, conn):
        self.conn = conn

    def __getitem__(self, item):
        """Create and return proxy around the method in the connection.

        :param item: name of the connection
        """
        return MongoProxy(self.conn[item])

    def find(self, *args, **kwargs):
        # We need this modifying method to return a CursorProxy object so that
        # we can handle the Cursor next function to catch the AutoReconnect
        # exception.
        return CursorProxy(self.conn.find(*args, **kwargs))

    def __getattr__(self, item):
        """Wrap MongoDB connection.

        If item is the name of an executable method, for example find or
        insert, wrap this method in the MongoConn.
        Else wrap getting attribute with MongoProxy.
        """
        if item in ('name', 'database'):
            return getattr(self.conn, item)
        if item in MONGO_METHODS:
            return MongoConn(getattr(self.conn, item))
        return MongoProxy(getattr(self.conn, item))

    def __call__(self, *args, **kwargs):
        return self.conn(*args, **kwargs)


class CursorProxy(pymongo.cursor.Cursor):
    def __init__(self, cursor):
        self.cursor = cursor

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
