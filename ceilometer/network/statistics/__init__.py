#
# Copyright 2014 NEC Corporation.  All rights reserved.
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

import abc

import six
from stevedore import extension

from ceilometer.central import plugin
from ceilometer import sample


@six.add_metaclass(abc.ABCMeta)
class _Base(plugin.CentralPollster):

    NAMESPACE = 'network.statistics.drivers'
    extension_manager = extension.ExtensionManager(namespace=NAMESPACE,
                                                   invoke_on_load=True)

    @abc.abstractproperty
    def meter_name(self):
        '''Return a Meter Name.'''

    @abc.abstractproperty
    def meter_type(self):
        '''Return a Meter Type.'''

    @abc.abstractproperty
    def meter_unit(self):
        '''Return a Meter Unit.'''

    def get_samples(self, manager, cache, resources=[]):
        for resource in resources:
            sample_data = self.extension_manager.map_method('get_sample_data',
                                                            self.meter_name,
                                                            resource,
                                                            cache)
            for data in sample_data:
                if data is None:
                    continue
                if not isinstance(data, list):
                    data = [data]
                for (volume, resource_id,
                     resource_metadata, timestamp) in data:

                    yield sample.Sample(
                        name=self.meter_name,
                        type=self.meter_type,
                        unit=self.meter_unit,
                        volume=volume,
                        user_id=None,
                        project_id=None,
                        resource_id=resource_id,
                        timestamp=timestamp,
                        resource_metadata=resource_metadata
                    )
