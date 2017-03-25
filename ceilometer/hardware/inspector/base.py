#
# Copyright 2014 ZHAW SoE
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
"""Inspector abstraction for read-only access to hardware components"""

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class Inspector(object):
    @abc.abstractmethod
    def inspect_generic(self, host, cache, extra_metadata, param):
        """A generic inspect function.

        :param host: the target host
        :param cache: cache passed from the pollster
        :param extra_metadata: extra dict to be used as metadata
        :param param: a dict of inspector specific param
        :return: an iterator of (value, metadata, extra) containing the sample
                 value, metadata dict to construct sample's metadata, and
                 extra dict of extra metadata to help constructing sample
        """

    def prepare_params(self, param):
        """Parse the params to a format which the inspector itself recognizes.

        :param param: inspector params from meter definition file
        :return: a dict of param which the inspector recognized
        """
        return {}
