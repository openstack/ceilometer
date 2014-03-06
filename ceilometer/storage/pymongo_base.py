# -*- encoding: utf-8 -*-
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

import pymongo
import weakref

from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import network_utils
from ceilometer.storage import base
from ceilometer.storage import models

LOG = log.getLogger(__name__)


def make_timestamp_range(start, end,
                         start_timestamp_op=None, end_timestamp_op=None):

    """Given two possible datetimes and their operations, create the query
    document to find timestamps within that range.
    By default, using $gte for the lower bound and $lt for the
    upper bound.
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

    :param filter: SampleFilter instance
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
                  for (k, v) in sample_filter.metaquery.iteritems()))
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
        splitted_url = network_utils.urlsplit(url)
        log_data = {'db': splitted_url.scheme,
                    'nodelist': connection_options['nodelist']}
        LOG.info(_('Connecting to %(db)s on %(nodelist)s') % log_data)
        client = pymongo.MongoClient(
            url,
            safe=True)
        self._pool[pool_key] = weakref.ref(client)
        return client


class Connection(base.Connection):
    """Base Connection class for MongoDB and DB2 drivers.
    """

    def get_users(self, source=None):
        """Return an iterable of user id strings.

        :param source: Optional source filter.
        """
        q = {}
        if source is not None:
            q['source'] = source

        return (doc['_id'] for doc in
                self.db.user.find(q, fields=['_id'],
                                  sort=[('_id', pymongo.ASCENDING)]))

    def get_projects(self, source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """
        q = {}
        if source is not None:
            q['source'] = source

        return (doc['_id'] for doc in
                self.db.project.find(q, fields=['_id'],
                                     sort=[('_id', pymongo.ASCENDING)]))

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
            raise NotImplementedError('Pagination not implemented')

        q = {}
        if user is not None:
            q['user_id'] = user
        if project is not None:
            q['project_id'] = project
        if resource is not None:
            q['_id'] = resource
        if source is not None:
            q['source'] = source
        q.update(metaquery)

        for r in self.db.resource.find(q):
            for r_meter in r['meter']:
                yield models.Meter(
                    name=r_meter['counter_name'],
                    type=r_meter['counter_type'],
                    # Return empty string if 'counter_unit' is not valid for
                    # backward compatibility.
                    unit=r_meter.get('counter_unit', ''),
                    resource_id=r['_id'],
                    project_id=r['project_id'],
                    source=r['source'],
                    user_id=r['user_id'],
                )

    def update_alarm(self, alarm):
        """update alarm
        """
        data = alarm.as_dict()

        self.db.alarm.update(
            {'alarm_id': alarm.alarm_id},
            {'$set': data},
            upsert=True)

        stored_alarm = self.db.alarm.find({'alarm_id': alarm.alarm_id})[0]
        del stored_alarm['_id']
        self._ensure_encapsulated_rule_format(stored_alarm)
        self._ensure_time_constraints(stored_alarm)
        return models.Alarm(**stored_alarm)

    create_alarm = update_alarm

    def delete_alarm(self, alarm_id):
        """Delete an alarm
        """
        self.db.alarm.remove({'alarm_id': alarm_id})

    def record_alarm_change(self, alarm_change):
        """Record alarm change event.
        """
        self.db.alarm_history.insert(alarm_change)

    def get_samples(self, sample_filter, limit=None):
        """Return an iterable of model.Sample instances.

        :param sample_filter: Filter.
        :param limit: Maximum number of results to return.
        """
        if limit == 0:
            return []
        q = make_query_from_filter(sample_filter,
                                   require_meter=False)

        return self._retrieve_samples(q,
                                      [("timestamp", pymongo.DESCENDING)],
                                      limit)

    def get_alarms(self, name=None, user=None,
                   project=None, enabled=None, alarm_id=None, pagination=None):
        """Yields a lists of alarms that match filters
        :param name: The Alarm name.
        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param enabled: Optional boolean to list disable alarm.
        :param alarm_id: Optional alarm_id to return one alarm.
        :param pagination: Optional pagination query.
        """
        if pagination:
            raise NotImplementedError('Pagination not implemented')

        q = {}
        if user is not None:
            q['user_id'] = user
        if project is not None:
            q['project_id'] = project
        if name is not None:
            q['name'] = name
        if enabled is not None:
            q['enabled'] = enabled
        if alarm_id is not None:
            q['alarm_id'] = alarm_id

        return self._retrieve_alarms(q, [], None)

    def get_alarm_changes(self, alarm_id, on_behalf_of,
                          user=None, project=None, type=None,
                          start_timestamp=None, start_timestamp_op=None,
                          end_timestamp=None, end_timestamp_op=None):
        """Yields list of AlarmChanges describing alarm history

        Changes are always sorted in reverse order of occurrence, given
        the importance of currency.

        Segregation for non-administrative users is done on the basis
        of the on_behalf_of parameter. This allows such users to have
        visibility on both the changes initiated by themselves directly
        (generally creation, rule changes, or deletion) and also on those
        changes initiated on their behalf by the alarming service (state
        transitions after alarm thresholds are crossed).

        :param alarm_id: ID of alarm to return changes for
        :param on_behalf_of: ID of tenant to scope changes query (None for
                             administrative user, indicating all projects)
        :param user: Optional ID of user to return changes for
        :param project: Optional ID of project to return changes for
        :project type: Optional change type
        :param start_timestamp: Optional modified timestamp start range
        :param start_timestamp_op: Optional timestamp start range operation
        :param end_timestamp: Optional modified timestamp end range
        :param end_timestamp_op: Optional timestamp end range operation
        """
        q = dict(alarm_id=alarm_id)
        if on_behalf_of is not None:
            q['on_behalf_of'] = on_behalf_of
        if user is not None:
            q['user_id'] = user
        if project is not None:
            q['project_id'] = project
        if type is not None:
            q['type'] = type
        if start_timestamp or end_timestamp:
            ts_range = make_timestamp_range(start_timestamp,
                                            end_timestamp,
                                            start_timestamp_op,
                                            end_timestamp_op)
            if ts_range:
                q['timestamp'] = ts_range

        return self._retrieve_alarm_changes(q,
                                            [("timestamp",
                                              pymongo.DESCENDING)],
                                            None)

    def query_samples(self, filter_expr=None, orderby=None, limit=None):
        return self._retrieve_data(filter_expr, orderby, limit, models.Meter)

    def query_alarms(self, filter_expr=None, orderby=None, limit=None):
        """Return an iterable of model.Alarm objects.
        """
        return self._retrieve_data(filter_expr, orderby, limit, models.Alarm)

    def query_alarm_history(self, filter_expr=None, orderby=None, limit=None):
        """Return an iterable of model.AlarmChange objects.
        """
        return self._retrieve_data(filter_expr,
                                   orderby,
                                   limit,
                                   models.AlarmChange)

    def _retrieve_data(self, filter_expr, orderby, limit, model):
        if limit == 0:
            return []
        query_filter = {}
        orderby_filter = [("timestamp", pymongo.DESCENDING)]
        transformer = QueryTransformer()
        if orderby is not None:
            orderby_filter = transformer.transform_orderby(orderby)
        if filter_expr is not None:
            query_filter = transformer.transform_filter(filter_expr)

        retrieve = {models.Meter: self._retrieve_samples,
                    models.Alarm: self._retrieve_alarms,
                    models.AlarmChange: self._retrieve_alarm_changes}
        return retrieve[model](query_filter, orderby_filter, limit)

    def _retrieve_samples(self, query, orderby, limit):
        if limit is not None:
            samples = self.db.meter.find(query,
                                         limit=limit,
                                         sort=orderby)
        else:
            samples = self.db.meter.find(query,
                                         sort=orderby)

        for s in samples:
            # Remove the ObjectId generated by the database when
            # the sample was inserted. It is an implementation
            # detail that should not leak outside of the driver.
            del s['_id']
            # Backward compatibility for samples without units
            s['counter_unit'] = s.get('counter_unit', '')
            # Tolerate absence of recorded_at in older datapoints
            s['recorded_at'] = s.get('recorded_at')
            yield models.Sample(**s)

    def _retrieve_alarms(self, query_filter, orderby, limit):
        if limit is not None:
            alarms = self.db.alarm.find(query_filter,
                                        limit=limit,
                                        sort=orderby)
        else:
            alarms = self.db.alarm.find(query_filter, sort=orderby)

        for alarm in alarms:
            a = {}
            a.update(alarm)
            del a['_id']
            self._ensure_encapsulated_rule_format(a)
            self._ensure_time_constraints(a)
            yield models.Alarm(**a)

    def _retrieve_alarm_changes(self, query_filter, orderby, limit):
        if limit is not None:
            alarms_history = self.db.alarm_history.find(query_filter,
                                                        limit=limit,
                                                        sort=orderby)
        else:
            alarms_history = self.db.alarm_history.find(
                query_filter, sort=orderby)

        for alarm_history in alarms_history:
            ah = {}
            ah.update(alarm_history)
            del ah['_id']
            yield models.AlarmChange(**ah)

    @classmethod
    def _ensure_encapsulated_rule_format(cls, alarm):
        """This ensure the alarm returned by the storage have the correct
        format. The previous format looks like:
        {
            'alarm_id': '0ld-4l3rt',
            'enabled': True,
            'name': 'old-alert',
            'description': 'old-alert',
            'timestamp': None,
            'meter_name': 'cpu',
            'user_id': 'me',
            'project_id': 'and-da-boys',
            'comparison_operator': 'lt',
            'threshold': 36,
            'statistic': 'count',
            'evaluation_periods': 1,
            'period': 60,
            'state': "insufficient data",
            'state_timestamp': None,
            'ok_actions': [],
            'alarm_actions': ['http://nowhere/alarms'],
            'insufficient_data_actions': [],
            'repeat_actions': False,
            'matching_metadata': {'key': 'value'}
            # or 'matching_metadata': [{'key': 'key', 'value': 'value'}]
        }
        """

        if isinstance(alarm.get('rule'), dict):
            return

        alarm['type'] = 'threshold'
        alarm['rule'] = {}
        alarm['matching_metadata'] = cls._decode_matching_metadata(
            alarm['matching_metadata'])
        for field in ['period', 'evaluation_periods', 'threshold',
                      'statistic', 'comparison_operator', 'meter_name']:
            if field in alarm:
                alarm['rule'][field] = alarm[field]
                del alarm[field]

        query = []
        for key in alarm['matching_metadata']:
            query.append({'field': key,
                          'op': 'eq',
                          'value': alarm['matching_metadata'][key],
                          'type': 'string'})
        del alarm['matching_metadata']
        alarm['rule']['query'] = query

    @staticmethod
    def _decode_matching_metadata(matching_metadata):
        if isinstance(matching_metadata, dict):
            #note(sileht): keep compatibility with alarm
            #with matching_metadata as a dict
            return matching_metadata
        else:
            new_matching_metadata = {}
            for elem in matching_metadata:
                new_matching_metadata[elem['key']] = elem['value']
            return new_matching_metadata

    @staticmethod
    def _ensure_time_constraints(alarm):
        """Ensures the alarm has a time constraints field."""
        if 'time_constraints' not in alarm:
            alarm['time_constraints'] = []


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
        """Moves every not operator to the leafs by
        applying the De Morgan rules and anihilating
        double negations
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
                    # two consecutive not annihilates theirselves
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
