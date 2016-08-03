#
# Copyright 2014 Cisco Systems,Inc.
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

from ceilometer.agent import plugin_base


# status map for converting metric status to volume int
STATUS = {
    'inactive': 0,
    'active': 1,
    'pending_create': 2,
    'down': 3,
    'created': 4,
    'pending_update': 5,
    'pending_delete': 6,
    'error': 7,
}


class BaseServicesPollster(plugin_base.PollsterBase):

    FIELDS = []

    def extract_metadata(self, metric):
        return dict((k, metric[k]) for k in self.FIELDS)

    @staticmethod
    def get_status_id(value):
        status = value.lower()
        return STATUS.get(status, -1)
