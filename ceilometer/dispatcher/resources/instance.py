#
# Copyright 2014 eNovance
#
# Authors: Julien Danjou <julien@danjou.info>
#          Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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

from ceilometer.dispatcher.resources import base


class Instance(base.ResourceBase):
    @staticmethod
    def get_resource_extra_attributes(sample):
        metadata = sample['resource_metadata']
        params = {
            "host": metadata['host'],
            "image_ref": metadata['image_ref_url'],
            "display_name": metadata['display_name'],
        }
        if "instance_flavor_id" in metadata:
            params["flavor_id"] = int(metadata['instance_flavor_id'])
        else:
            # NOTE(sileht): instance.exists have the flavor here
            params["flavor_id"] = int(metadata["flavor"]["id"])

        server_group = metadata.get('user_metadata', {}).get('server_group')
        if server_group:
            params["server_group"] = server_group

        return params

    @staticmethod
    def get_metrics_names():
        # NOTE(sileht): Can we generate the list by loading ceilometer
        # plugin ?
        return ['instance',
                'disk.root.size',
                'disk.ephemeral.size',
                'memory',
                'memory.usage',
                'vcpus',
                'cpu',
                'cpu_util']
