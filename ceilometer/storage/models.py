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
from ceilometer.storage import base


class Resource(base.Model):
    """Something for which sample data has been collected."""

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
        base.Model.__init__(self,
                            resource_id=resource_id,
                            first_sample_timestamp=first_sample_timestamp,
                            last_sample_timestamp=last_sample_timestamp,
                            project_id=project_id,
                            source=source,
                            user_id=user_id,
                            metadata=metadata,
                            )


class Meter(base.Model):
    """Definition of a meter for which sample data has been collected."""

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
        base.Model.__init__(self,
                            name=name,
                            type=type,
                            unit=unit,
                            resource_id=resource_id,
                            project_id=project_id,
                            source=source,
                            user_id=user_id,
                            )


class Sample(base.Model):
    """One collected data point."""
    def __init__(self,
                 source,
                 counter_name, counter_type, counter_unit, counter_volume,
                 user_id, project_id, resource_id,
                 timestamp, resource_metadata,
                 message_id,
                 message_signature,
                 recorded_at,
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
        :param recorded_at: sample record timestamp
        :param message_signature: a hash created from the rest of the
        message data
        """
        base.Model.__init__(self,
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
                            message_signature=message_signature,
                            recorded_at=recorded_at)


class Statistics(base.Model):
    """Computed statistics based on a set of sample data."""
    def __init__(self, unit,
                 period, period_start, period_end,
                 duration, duration_start, duration_end,
                 groupby, **data):
        """Create a new statistics object.

        :param unit: The unit type of the data set
        :param period: The length of the time range covered by these stats
        :param period_start: The timestamp for the start of the period
        :param period_end: The timestamp for the end of the period
        :param duration: The total time for the matching samples
        :param duration_start: The earliest time for the matching samples
        :param duration_end: The latest time for the matching samples
        :param groupby: The fields used to group the samples.
        :param data: some or all of the following aggregates
           min: The smallest volume found
           max: The largest volume found
           avg: The average of all volumes found
           sum: The total of all volumes found
           count: The number of samples found
           aggregate: name-value pairs for selectable aggregates
        """
        base.Model.__init__(self, unit=unit,
                            period=period, period_start=period_start,
                            period_end=period_end, duration=duration,
                            duration_start=duration_start,
                            duration_end=duration_end,
                            groupby=groupby,
                            **data)
