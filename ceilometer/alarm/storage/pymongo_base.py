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

from oslo_log import log
import pymongo

from ceilometer.alarm.storage import base
from ceilometer.alarm.storage import models
from ceilometer.storage.mongo import utils as pymongo_utils
from ceilometer import utils

LOG = log.getLogger(__name__)


COMMON_AVAILABLE_CAPABILITIES = {
    'alarms': {'query': {'simple': True,
                         'complex': True},
               'history': {'query': {'simple': True,
                                     'complex': True}}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


class Connection(base.Connection):
    """Base Alarm Connection class for MongoDB and DB2 drivers."""
    CAPABILITIES = utils.update_nested(base.Connection.CAPABILITIES,
                                       COMMON_AVAILABLE_CAPABILITIES)

    STORAGE_CAPABILITIES = utils.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )

    def upgrade(self):
        # create collection if not present
        if 'alarm' not in self.db.conn.collection_names():
            self.db.conn.create_collection('alarm')
        if 'alarm_history' not in self.db.conn.collection_names():
            self.db.conn.create_collection('alarm_history')

    def update_alarm(self, alarm):
        """Update alarm."""
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
        """Delete an alarm and its history data."""
        self.db.alarm.remove({'alarm_id': alarm_id})
        self.db.alarm_history.remove({'alarm_id': alarm_id})

    def record_alarm_change(self, alarm_change):
        """Record alarm change event."""
        self.db.alarm_history.insert(alarm_change.copy())

    def get_alarms(self, name=None, user=None, state=None, meter=None,
                   project=None, enabled=None, alarm_id=None,
                   alarm_type=None, severity=None):
        """Yields a lists of alarms that match filters.

        :param name: Optional name for alarm.
        :param user: Optional ID for user that owns the resource.
        :param state: Optional string for alarm state.
        :param meter: Optional string for alarms associated with meter.
        :param project: Optional ID for project that owns the resource.
        :param enabled: Optional boolean to list disable alarm.
        :param alarm_id: Optional alarm_id to return one alarm.
        :param alarm_type: Optional alarm type.
        :param severity: Optional alarm severity.
        """
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
        if state is not None:
            q['state'] = state
        if meter is not None:
            q['rule.meter_name'] = meter
        if alarm_type is not None:
            q['type'] = alarm_type
        if severity is not None:
            q['severity'] = severity

        return self._retrieve_alarms(q,
                                     [("timestamp",
                                       pymongo.DESCENDING)],
                                     None)

    def get_alarm_changes(self, alarm_id, on_behalf_of,
                          user=None, project=None, alarm_type=None,
                          severity=None, start_timestamp=None,
                          start_timestamp_op=None, end_timestamp=None,
                          end_timestamp_op=None):
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
        :param alarm_type: Optional change type
        :param severity: Optional change severity
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
        if alarm_type is not None:
            q['type'] = alarm_type
        if severity is not None:
            q['severity'] = severity
        if start_timestamp or end_timestamp:
            ts_range = pymongo_utils.make_timestamp_range(start_timestamp,
                                                          end_timestamp,
                                                          start_timestamp_op,
                                                          end_timestamp_op)
            if ts_range:
                q['timestamp'] = ts_range

        return self._retrieve_alarm_changes(q,
                                            [("timestamp",
                                              pymongo.DESCENDING)],
                                            None)

    def query_alarms(self, filter_expr=None, orderby=None, limit=None):
        """Return an iterable of model.Alarm objects."""
        return self._retrieve_data(filter_expr, orderby, limit,
                                   models.Alarm)

    def query_alarm_history(self, filter_expr=None, orderby=None, limit=None):
        """Return an iterable of model.AlarmChange objects."""
        return self._retrieve_data(filter_expr,
                                   orderby,
                                   limit,
                                   models.AlarmChange)

    def _retrieve_data(self, filter_expr, orderby, limit, model):
        if limit == 0:
            return []
        query_filter = {}
        orderby_filter = [("timestamp", pymongo.DESCENDING)]
        transformer = pymongo_utils.QueryTransformer()
        if orderby is not None:
            orderby_filter = transformer.transform_orderby(orderby)
        if filter_expr is not None:
            query_filter = transformer.transform_filter(filter_expr)

        retrieve = {models.Alarm: self._retrieve_alarms,
                    models.AlarmChange: self._retrieve_alarm_changes}
        return retrieve[model](query_filter, orderby_filter, limit)

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
        """Ensure the alarm returned by the storage have the correct format.

        The previous format looks like:
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
            # note(sileht): keep compatibility with alarm
            # with matching_metadata as a dict
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
