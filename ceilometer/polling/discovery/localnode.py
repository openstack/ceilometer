# Copyright 2015 Intel
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

from ceilometer.polling import plugin_base


class LocalNodeDiscovery(plugin_base.DiscoveryBase):
    def discover(self, manager, param=None):
        """Return local node as resource."""
        return [self.conf.host]

    @property
    def group_id(self):
        return "LocalNode-%s" % self.conf.host
