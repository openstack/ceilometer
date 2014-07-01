#
# Copyright 2013 ZHAW SoE
# Copyright 2014 Intel Corp.
#
# Authors: Lucas Graf <graflu0@students.zhaw.ch>
#          Toni Zehnder <zehndton@students.zhaw.ch>
#          Lianhao Lu <lianhao.lu@intel.com>
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

from ceilometer.openstack.common import timeutils
from ceilometer import sample


def get_metadata_from_host(host_url):
    return {'resource_url': urlparse.urlunsplit(host_url)}


def make_sample_from_host(host_url, name, type, unit, volume,
                          project_id=None, user_id=None, res_metadata=None):
    resource_metadata = dict()
    if res_metadata is not None:
        metadata = copy.copy(res_metadata)
        resource_metadata = dict(zip(metadata._fields, metadata))
    resource_metadata.update(get_metadata_from_host(host_url))

    return sample.Sample(
        name='hardware.' + name,
        type=type,
        unit=unit,
        volume=volume,
        user_id=project_id,
        project_id=user_id,
        resource_id=host_url.hostname,
        timestamp=timeutils.isotime(),
        resource_metadata=resource_metadata,
        source='hardware',
    )
