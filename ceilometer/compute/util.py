#
# Copyright 2014 Red Hat, Inc
#
# Author: Eoghan Glynn <eglynn@redhat.com>
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

from oslo.config import cfg
import six


OPTS = [
    cfg.ListOpt('reserved_metadata_namespace',
                default=['metering.'],
                help='List of metadata prefixes reserved for metering use.'),
    cfg.IntOpt('reserved_metadata_length',
               default=256,
               help='Limit on length of reserved metadata values.'),
]

cfg.CONF.register_opts(OPTS)


def add_reserved_user_metadata(src_metadata, dest_metadata):
    limit = cfg.CONF.reserved_metadata_length
    user_metadata = {}
    for prefix in cfg.CONF.reserved_metadata_namespace:
        md = dict(
            (k[len(prefix):].replace('.', '_'),
             v[:limit] if isinstance(v, six.string_types) else v)
            for k, v in src_metadata.items()
            if (k.startswith(prefix) and
                k[len(prefix):].replace('.', '_') not in dest_metadata)
        )
        user_metadata.update(md)
    if user_metadata:
        dest_metadata['user_metadata'] = user_metadata

    return dest_metadata
