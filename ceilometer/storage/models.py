# -*- encoding: utf-8 -*-
#
# Copyright © 2013 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
import inspect

from ceilometer.openstack.common import timeutils


class Model(object):
    """Base class for storage API models.
    """

    def __init__(self, **kwds):
        self.fields = list(kwds)
        for k, v in kwds.iteritems():
            setattr(self, k, v)

    def as_dict(self):
        d = {}
        for f in self.fields:
            v = getattr(self, f)
            if isinstance(v, Model):
                v = v.as_dict()
            elif isinstance(v, list) and v and isinstance(v[0], Model):
                v = [sub.as_dict() for sub in v]
            d[f] = v
        return d

    def __eq__(self, other):
        return self.as_dict() == other.as_dict()

    @classmethod
    def get_field_names(cls):
        fields = inspect.getargspec(cls.__init__)[0]
        return set(fields) - set(["self"])


class Event(Model):
    """A raw event from the source system. Events have Traits.

       Metrics will be derived from one or more Events.
    """

    DUPLICATE = 1
    UNKNOWN_PROBLEM = 2

    def __init__(self, message_id, event_type, generated, traits):
        """Create a new event.

        :param message_id:  Unique ID for the message this event
                            stemmed from. This is different than
                            the Event ID, which comes from the
                            underlying storage system.
        :param event_type:  The type of the event.
        :param generated:   UTC time for when the event occurred.
        :param traits:      list of Traits on this Event.
        """
        Model.__init__(self, message_id=message_id, event_type=event_type,
                       generated=generated, traits=traits)

    def append_trait(self, trait_model):
        self.traits.append(trait_model)

    def __repr__(self):
        trait_list = []
        if self.traits:
            trait_list = [str(trait) for trait in self.traits]
        return "<Event: %s, %s, %s, %s>" % \
            (self.message_id, self.event_type, self.generated,
             " ".join(trait_list))


class Trait(Model):
    """A Trait is a key/value pair of data on an Event. The value is variant
    record of basic data types (int, date, float, etc).
    """

    NONE_TYPE = 0
    TEXT_TYPE = 1
    INT_TYPE = 2
    FLOAT_TYPE = 3
    DATETIME_TYPE = 4

    type_names = {
        NONE_TYPE: "none",
        TEXT_TYPE: "string",
        INT_TYPE: "integer",
        FLOAT_TYPE: "float",
        DATETIME_TYPE: "datetime"
    }

    def __init__(self, name, dtype, value):
        if not dtype:
            dtype = Trait.NONE_TYPE
        Model.__init__(self, name=name, dtype=dtype, value=value)

    def __repr__(self):
        return "<Trait: %s %d %s>" % (self.name, self.dtype, self.value)

    def get_type_name(self):
        return self.get_name_by_type(self.dtype)

    @classmethod
    def get_type_by_name(cls, type_name):
        return getattr(cls, '%s_TYPE' % type_name.upper(), None)

    @classmethod
    def get_type_names(cls):
        return cls.type_names.values()

    @classmethod
    def get_name_by_type(cls, type_id):
        return cls.type_names.get(type_id, "none")

    @classmethod
    def convert_value(cls, trait_type, value):
        if trait_type is cls.INT_TYPE:
            return int(value)
        if trait_type is cls.FLOAT_TYPE:
            return float(value)
        if trait_type is cls.DATETIME_TYPE:
            return timeutils.normalize_time(timeutils.parse_isotime(value))
        return str(value)


class Resource(Model):
    """Something for which sample data has been collected.
    """

    def __init__(self, resource_id, project_id,
                 first_sample_timestamp,
                 last_sample_timestamp,
                 source, user_id, metadata):
        """Create a new resource.

        :param resource_id: UUID of the resource
        :param project_id:  UUID of project owning the resource
        :param first_sample_timestamp: first sample timestamp captured
        :param last_sample_timestamp: last sample timestamp captured
        :param source:      the identifier for the user/project id definition
        :param user_id:     UUID of user owning the resource
        :param metadata:    most current metadata for the resource (a dict)
        """
        Model.__init__(self,
                       resource_id=resource_id,
                       first_sample_timestamp=first_sample_timestamp,
                       last_sample_timestamp=last_sample_timestamp,
                       project_id=project_id,
                       source=source,
                       user_id=user_id,
                       metadata=metadata,
                       )


class Meter(Model):
    """Definition of a meter for which sample data has been collected.
    """

    def __init__(self, name, type, unit, resource_id, project_id, source,
                 user_id):
        """Create a new meter.

        :param name: name of the meter
        :param type: type of the meter (gauge, delta, cumulative)
        :param unit: unit of the meter
        :param resource_id: UUID of the resource
        :param project_id: UUID of project owning the resource
        :param source: the identifier for the user/project id definition
        :param user_id: UUID of user owning the resource
        """
        Model.__init__(self,
                       name=name,
                       type=type,
                       unit=unit,
                       resource_id=resource_id,
                       project_id=project_id,
                       source=source,
                       user_id=user_id,
                       )


class Sample(Model):
    """One collected data point.
    """
    def __init__(self,
                 source,
                 counter_name, counter_type, counter_unit, counter_volume,
                 user_id, project_id, resource_id,
                 timestamp, resource_metadata,
                 message_id,
                 message_signature,
                 ):
        """Create a new sample.

        :param source: the identifier for the user/project id definition
        :param counter_name: the name of the measurement being taken
        :param counter_type: the type of the measurement
        :param counter_unit: the units for the measurement
        :param counter_volume: the measured value
        :param user_id: the user that triggered the measurement
        :param project_id: the project that owns the resource
        :param resource_id: the thing on which the measurement was taken
        :param timestamp: the time of the measurement
        :param resource_metadata: extra details about the resource
        :param message_id: a message identifier
        :param message_signature: a hash created from the rest of the
                                  message data
        """
        Model.__init__(self,
                       source=source,
                       counter_name=counter_name,
                       counter_type=counter_type,
                       counter_unit=counter_unit,
                       counter_volume=counter_volume,
                       user_id=user_id,
                       project_id=project_id,
                       resource_id=resource_id,
                       timestamp=timestamp,
                       resource_metadata=resource_metadata,
                       message_id=message_id,
                       message_signature=message_signature)


class Statistics(Model):
    """Computed statistics based on a set of sample data.
    """
    def __init__(self, unit,
                 min, max, avg, sum, count,
                 period, period_start, period_end,
                 duration, duration_start, duration_end,
                 groupby):
        """Create a new statistics object.

        :param unit: The unit type of the data set
        :param min: The smallest volume found
        :param max: The largest volume found
        :param avg: The average of all volumes found
        :param sum: The total of all volumes found
        :param count: The number of samples found
        :param period: The length of the time range covered by these stats
        :param period_start: The timestamp for the start of the period
        :param period_end: The timestamp for the end of the period
        :param duration: The total time for the matching samples
        :param duration_start: The earliest time for the matching samples
        :param duration_end: The latest time for the matching samples
        :param groupby: The fields used to group the samples.
        """
        Model.__init__(self, unit=unit,
                       min=min, max=max, avg=avg, sum=sum, count=count,
                       period=period, period_start=period_start,
                       period_end=period_end, duration=duration,
                       duration_start=duration_start,
                       duration_end=duration_end,
                       groupby=groupby)


class Alarm(Model):
    ALARM_INSUFFICIENT_DATA = 'insufficient data'
    ALARM_OK = 'ok'
    ALARM_ALARM = 'alarm'

    ALARM_ACTIONS_MAP = {
        ALARM_INSUFFICIENT_DATA: 'insufficient_data_actions',
        ALARM_OK: 'ok_actions',
        ALARM_ALARM: 'alarm_actions',
    }

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
    :param timestamp: the timestamp when the alarm was last updated
    :param state_timestamp: the timestamp of the last state change
    :param ok_actions: the list of webhooks to call when entering the ok state
    :param alarm_actions: the list of webhooks to call when entering the
                          alarm state
    :param insufficient_data_actions: the list of webhooks to call when
                                      entering the insufficient data state
    :param repeat_actions: Is the actions should be triggered on each
                           alarm evaluation.
    """
    def __init__(self, alarm_id, type, enabled, name, description,
                 timestamp, user_id, project_id, state, state_timestamp,
                 ok_actions, alarm_actions, insufficient_data_actions,
                 repeat_actions, rule):
        Model.__init__(
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
            insufficient_data_actions=
            insufficient_data_actions,
            repeat_actions=repeat_actions,
            rule=rule)


class AlarmChange(Model):
    """Record of an alarm change.

    :param event_id: UUID of the change event
    :param alarm_id: UUID of the alarm
    :param type: The type of change
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
    DELETION = 'deletion'

    def __init__(self,
                 event_id,
                 alarm_id,
                 type,
                 detail,
                 user_id,
                 project_id,
                 on_behalf_of,
                 timestamp=None
                 ):
        Model.__init__(
            self,
            event_id=event_id,
            alarm_id=alarm_id,
            type=type,
            detail=detail,
            user_id=user_id,
            project_id=project_id,
            on_behalf_of=on_behalf_of,
            timestamp=timestamp)
