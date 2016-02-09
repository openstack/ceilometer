#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 eNovance
#
# Authors: Doug Hellmann <doug.hellmann@dreamhost.com>
#          Julien Danjou <julien@danjou.info>
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
"""Sample class for holding data about a metering event.

A Sample doesn't really do anything, but we need a way to
ensure that all of the appropriate fields have been filled
in by the plugins that create them.
"""

import copy
import uuid

from oslo_config import cfg


OPTS = [
    cfg.StrOpt('sample_source',
               default='openstack',
               help='Source for samples emitted on this instance.'),
]

cfg.CONF.register_opts(OPTS)


# Fields explanation:
#
# Source: the source of this sample
# Name: the name of the meter, must be unique
# Type: the type of the meter, must be either:
#       - cumulative: the value is incremented and never reset to 0
#       - delta: the value is reset to 0 each time it is sent
#       - gauge: the value is an absolute value and is not a counter
# Unit: the unit of the meter
# Volume: the sample value
# User ID: the user ID
# Project ID: the project ID
# Resource ID: the resource ID
# Timestamp: when the sample has been read
# Resource metadata: various metadata
# id: an uuid of a sample, can be taken from API  when post sample via API
class Sample(object):

    def __init__(self, name, type, unit, volume, user_id, project_id,
                 resource_id, timestamp, resource_metadata, source=None,
                 id=None):
        self.name = name
        self.type = type
        self.unit = unit
        self.volume = volume
        self.user_id = user_id
        self.project_id = project_id
        self.resource_id = resource_id
        self.timestamp = timestamp
        self.resource_metadata = resource_metadata
        self.source = source or cfg.CONF.sample_source
        self.id = id or str(uuid.uuid1())

    def as_dict(self):
        return copy.copy(self.__dict__)

    def __repr__(self):
        return '<name: %s, volume: %s, resource_id: %s, timestamp: %s>' % (
            self.name, self.volume, self.resource_id, self.timestamp)

    @classmethod
    def from_notification(cls, name, type, volume, unit,
                          user_id, project_id, resource_id,
                          message, timestamp=None, metadata=None, source=None):
        if not metadata:
            metadata = (copy.copy(message['payload'])
                        if isinstance(message['payload'], dict) else {})
            metadata['event_type'] = message['event_type']
            metadata['host'] = message['publisher_id']
        ts = timestamp if timestamp else message['timestamp']
        return cls(name=name,
                   type=type,
                   volume=volume,
                   unit=unit,
                   user_id=user_id,
                   project_id=project_id,
                   resource_id=resource_id,
                   timestamp=ts,
                   resource_metadata=metadata,
                   source=source)

TYPE_GAUGE = 'gauge'
TYPE_DELTA = 'delta'
TYPE_CUMULATIVE = 'cumulative'

TYPES = (TYPE_GAUGE, TYPE_DELTA, TYPE_CUMULATIVE)
