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


@six.add_metaclass(abc.ABCMeta)
class Driver(object):
    def __init__(self, conf):
        self.conf = conf

    @abc.abstractmethod
    def get_sample_data(self, meter_name, parse_url, params, cache):
        """Return volume, resource_id, resource_metadata, timestamp in tuple.

        If not implemented for meter_name, returns None
        """
