#
# Copyright 2014 Cisco Systems,Inc.
#
# Author: Pradeep Kilambi <pkilambi@cisco.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from ceilometer import neutron_client
from ceilometer.openstack.common import log
from ceilometer import plugin

LOG = log.getLogger(__name__)


# status map for converting metric status to volume int
STATUS = {
    'inactive': 0,
    'active': 1,
    'pending_create': 2,
}


class BaseServicesPollster(plugin.PollsterBase):

    FIELDS = []
    nc = neutron_client.Client()

    def _iter_cache(self, cache, meter_name, method):
        if meter_name not in cache:
            cache[meter_name] = list(method())
        return iter(cache[meter_name])

    def extract_metadata(self, metric):
        return dict((k, metric[k]) for k in self.FIELDS)

    @staticmethod
    def get_status_id(value):
        status = value.lower()
        return STATUS.get(status, -1)
