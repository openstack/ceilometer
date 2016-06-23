#
# Copyright 2013 ZHAW SoE
# Copyright 2014 Intel Corp.
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

import copy

from six.moves.urllib import parse as urlparse

from ceilometer import sample


def get_metadata_from_host(host_url):
    return {'resource_url': urlparse.urlunsplit(host_url)}


def make_resource_metadata(res_metadata=None, host_url=None):
    resource_metadata = dict()
    if res_metadata is not None:
        metadata = copy.copy(res_metadata)
        resource_metadata.update(metadata)
    resource_metadata.update(get_metadata_from_host(host_url))
    return resource_metadata


def make_sample_from_host(host_url, name, sample_type, unit, volume,
                          project_id=None, user_id=None, resource_id=None,
                          res_metadata=None, extra=None,
                          name_prefix='hardware'):

    extra = extra or {}
    resource_metadata = make_resource_metadata(res_metadata, host_url)
    resource_metadata.update(extra)

    res_id = resource_id or extra.get('resource_id') or host_url.hostname
    if name_prefix:
        name = name_prefix + '.' + name
    return sample.Sample(
        name=name,
        type=sample_type,
        unit=unit,
        volume=volume,
        user_id=user_id or extra.get('user_id'),
        project_id=project_id or extra.get('project_id'),
        resource_id=res_id,
        resource_metadata=resource_metadata,
        source='hardware',
    )
