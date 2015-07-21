# Copyright 2014 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ceilometer.tests.functional import api

V2_MEDIA_TYPES = [
    {
        'base': 'application/json',
        'type': 'application/vnd.openstack.telemetry-v2+json'
    }, {
        'base': 'application/xml',
        'type': 'application/vnd.openstack.telemetry-v2+xml'
    }
]

V2_HTML_DESCRIPTION = {
    'href': 'http://docs.openstack.org/',
    'rel': 'describedby',
    'type': 'text/html',
}

V2_EXPECTED_RESPONSE = {
    'id': 'v2',
    'links': [
        {
            'rel': 'self',
            'href': 'http://localhost/v2',
        },
        V2_HTML_DESCRIPTION
    ],
    'media-types': V2_MEDIA_TYPES,
    'status': 'stable',
    'updated': '2013-02-13T00:00:00Z',
}

V2_VERSION_RESPONSE = {
    "version": V2_EXPECTED_RESPONSE
}

VERSIONS_RESPONSE = {
    "versions": {
        "values": [
            V2_EXPECTED_RESPONSE
        ]
    }
}


class TestVersions(api.FunctionalTest):

    def test_versions(self):
        data = self.get_json('/')
        self.assertEqual(VERSIONS_RESPONSE, data)
