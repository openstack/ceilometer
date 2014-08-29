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

from oslo.config import cfg
from oslo.utils import netutils
import pymongo
import six
import weakref

from ceilometer.openstack.common.gettextutils import _
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
    q = {}
    ts_range = make_timestamp_range(event_filter.start_time,
                                    event_filter.end_time)
    if ts_range:
        q['timestamp'] = ts_range
    if event_filter.event_type:
        q['event_type'] = event_filter.event_type
    if event_filter.message_id:
        q['_id'] = event_filter.message_id

    if event_filter.traits_filter:
        q.setdefault('traits')
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
            if q['traits'] is None:
                q['traits'] = dict_query
            elif q.get('$and') is None:
                q.setdefault('$and', [{'traits': q.pop('traits')},
                                      {'traits': dict_query}])
            else:
                q['$and'].append({'traits': dict_query})
    return q


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

    ts_range = make_timestamp_range(sample_filter.start,
                                    sample_filter.end,
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
    q.update(dict(('resource_%s' % k, v)
                  for (k, v) in six.iteritems(sample_filter.metaquery)))
    return q


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
        max_retries = cfg.CONF.database.max_retries
        retry_interval = cfg.CONF.database.retry_interval
        attempts = 0
        while True:
            try:
                client = pymongo.MongoClient(url, safe=True)
            except pymongo.errors.ConnectionFailure as e:
                if 0 <= max_retries <= attempts:
                    LOG.error(_('Unable to connect to the database after '
                                '%(retries)d retries. Giving up.') %
                              {'retries': max_retries})
                    raise
                LOG.warn(_('Unable to connect to the database server: '
                           '%(errmsg)s. Trying again in %(retry_interval)d '
                           'seconds.') %
                         {'errmsg': e, 'retry_interval': retry_interval})
                attempts += 1
                time.sleep(retry_interval)
            else:
                return client


class QueryTransformer(object):

    operators = {"<": "$lt",
                 ">": "$gt",
                 "<=": "$lte",
                 "=<": "$lte",
                 ">=": "$gte",
                 "=>": "$gte",
                 "!=": "$ne",
                 "in": "$in"}

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
