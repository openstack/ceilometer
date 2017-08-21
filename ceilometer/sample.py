#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 eNovance
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
from oslo_utils import timeutils
import six

OPTS = [
    cfg.StrOpt('sample_source',
               default='openstack',
               help='Source for samples emitted on this instance.'),
    cfg.ListOpt('reserved_metadata_namespace',
                default=['metering.'],
                help='List of metadata prefixes reserved for metering use.'),
    cfg.IntOpt('reserved_metadata_length',
               default=256,
               help='Limit on length of reserved metadata values.'),
    cfg.ListOpt('reserved_metadata_keys',
                default=[],
                help='List of metadata keys reserved for metering use. And '
                     'these keys are additional to the ones included in the '
                     'namespace.'),
]


def add_reserved_user_metadata(conf, src_metadata, dest_metadata):
    limit = conf.reserved_metadata_length
    user_metadata = {}
    for prefix in conf.reserved_metadata_namespace:
        md = dict(
            (k[len(prefix):].replace('.', '_'),
             v[:limit] if isinstance(v, six.string_types) else v)
            for k, v in src_metadata.items()
            if (k.startswith(prefix) and
                k[len(prefix):].replace('.', '_') not in dest_metadata)
        )
        user_metadata.update(md)

    for metadata_key in conf.reserved_metadata_keys:
        md = dict(
            (k.replace('.', '_'),
             v[:limit] if isinstance(v, six.string_types) else v)
            for k, v in src_metadata.items()
            if (k == metadata_key and
                k.replace('.', '_') not in dest_metadata)
        )
        user_metadata.update(md)

    if user_metadata:
        dest_metadata['user_metadata'] = user_metadata

    return dest_metadata


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
    SOURCE_DEFAULT = "openstack"

    def __init__(self, name, type, unit, volume, user_id, project_id,
                 resource_id, timestamp=None, resource_metadata=None,
                 source=None, id=None, monotonic_time=None):
        self.name = name
        self.type = type
        self.unit = unit
        self.volume = volume
        self.user_id = user_id
        self.project_id = project_id
        self.resource_id = resource_id
        self.timestamp = timestamp
        self.resource_metadata = resource_metadata or {}
        self.source = source or self.SOURCE_DEFAULT
        self.id = id or str(uuid.uuid1())
        self.monotonic_time = monotonic_time

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
        ts = timestamp if timestamp else message['metadata']['timestamp']
        ts = timeutils.parse_isotime(ts).isoformat()  # add UTC if necessary
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

    def set_timestamp(self, timestamp):
        self.timestamp = timestamp

    def get_iso_timestamp(self):
        return timeutils.parse_isotime(self.timestamp)


def setup(conf):
    # NOTE(sileht): Instead of passing the cfg.CONF everywhere in ceilometer
    # prepare_service will override this default
    Sample.SOURCE_DEFAULT = conf.sample_source


TYPE_GAUGE = 'gauge'
TYPE_DELTA = 'delta'
TYPE_CUMULATIVE = 'cumulative'

TYPES = (TYPE_GAUGE, TYPE_DELTA, TYPE_CUMULATIVE)
