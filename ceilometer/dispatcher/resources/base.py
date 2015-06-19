#
# Copyright 2014 eNovance
#
# Authors: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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


@six.add_metaclass(abc.ABCMeta)
class ResourceBase(object):
    """Base class for resource."""

    @abc.abstractmethod
    def get_resource_extra_attributes(self, sample):
        """Extract the metadata from a ceilometer sample.

        :param sample: The ceilometer sample
        :returns: the resource attributes
        """

    @abc.abstractmethod
    def get_metrics_names(self):
        """Return the metric handled by this resource.

        :returns: list of metric names
        """
