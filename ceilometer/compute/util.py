#
# Copyright 2014 Red Hat, Inc
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

from oslo_config import cfg
import six


# Below config is for collecting metadata which user defined in nova or else,
# and then storing it to Sample for future use according to user's requirement.
# Such as using it as OpenTSDB tags for metrics.
OPTS = [
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

cfg.CONF.register_opts(OPTS)


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
