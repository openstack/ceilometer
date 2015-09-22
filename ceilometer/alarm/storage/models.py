#
# Copyright 2013 New Dream Network, LLC (DreamHost)
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
"""Model classes for use in the storage API.
"""

import datetime

from ceilometer.i18n import _
from ceilometer.storage import base


class Alarm(base.Model):
    ALARM_INSUFFICIENT_DATA = 'insufficient data'
    ALARM_OK = 'ok'
    ALARM_ALARM = 'alarm'

    ALARM_ACTIONS_MAP = {
        ALARM_INSUFFICIENT_DATA: 'insufficient_data_actions',
        ALARM_OK: 'ok_actions',
        ALARM_ALARM: 'alarm_actions',
    }

    ALARM_LEVEL_LOW = 'low'
    ALARM_LEVEL_MODERATE = 'moderate'
    ALARM_LEVEL_CRITICAL = 'critical'

    """
    An alarm to monitor.

    :param alarm_id: UUID of the alarm
    :param type: type of the alarm
    :param name: The Alarm name
    :param description: User friendly description of the alarm
    :param enabled: Is the alarm enabled
    :param state: Alarm state (ok/alarm/insufficient data)
    :param rule: A rule that defines when the alarm fires
    :param user_id: the owner/creator of the alarm
    :param project_id: the project_id of the creator
    :param evaluation_periods: the number of periods
    :param period: the time period in seconds
    :param time_constraints: the list of the alarm's time constraints, if any
    :param timestamp: the timestamp when the alarm was last updated
    :param state_timestamp: the timestamp of the last state change
    :param ok_actions: the list of webhooks to call when entering the ok state
    :param alarm_actions: the list of webhooks to call when entering the
                          alarm state
    :param insufficient_data_actions: the list of webhooks to call when
                                      entering the insufficient data state
    :param repeat_actions: Is the actions should be triggered on each
                           alarm evaluation.
    :param severity: Alarm level (low/moderate/critical)
    """
    def __init__(self, alarm_id, type, enabled, name, description,
                 timestamp, user_id, project_id, state, state_timestamp,
                 ok_actions, alarm_actions, insufficient_data_actions,
                 repeat_actions, rule, time_constraints, severity=None):
        if not isinstance(timestamp, datetime.datetime):
            raise TypeError(_("timestamp should be datetime object"))
        if not isinstance(state_timestamp, datetime.datetime):
            raise TypeError(_("state_timestamp should be datetime object"))
        base.Model.__init__(
            self,
            alarm_id=alarm_id,
            type=type,
            enabled=enabled,
            name=name,
            description=description,
            timestamp=timestamp,
            user_id=user_id,
            project_id=project_id,
            state=state,
            state_timestamp=state_timestamp,
            ok_actions=ok_actions,
            alarm_actions=alarm_actions,
            insufficient_data_actions=insufficient_data_actions,
            repeat_actions=repeat_actions,
            rule=rule,
            time_constraints=time_constraints,
            severity=severity)


class AlarmChange(base.Model):
    """Record of an alarm change.

    :param event_id: UUID of the change event
    :param alarm_id: UUID of the alarm
    :param type: The type of change
    :param severity: The severity of alarm
    :param detail: JSON fragment describing change
    :param user_id: the user ID of the initiating identity
    :param project_id: the project ID of the initiating identity
    :param on_behalf_of: the tenant on behalf of which the change
                         is being made
    :param timestamp: the timestamp of the change
    """

    CREATION = 'creation'
    RULE_CHANGE = 'rule change'
    STATE_TRANSITION = 'state transition'

    def __init__(self,
                 event_id,
                 alarm_id,
                 type,
                 detail,
                 user_id,
                 project_id,
                 on_behalf_of,
                 severity=None,
                 timestamp=None
                 ):
        base.Model.__init__(
            self,
            event_id=event_id,
            alarm_id=alarm_id,
            type=type,
            severity=severity,
            detail=detail,
            user_id=user_id,
            project_id=project_id,
            on_behalf_of=on_behalf_of,
            timestamp=timestamp)
