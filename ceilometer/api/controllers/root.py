#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

import pecan

from ceilometer.api.controllers.v2 import root as v2

MEDIA_TYPE_JSON = 'application/vnd.openstack.telemetry-%s+json'
MEDIA_TYPE_XML = 'application/vnd.openstack.telemetry-%s+xml'


class RootController(object):

    def __init__(self):
        self.v2 = v2.V2Controller()

    @pecan.expose('json')
    def index(self):
        base_url = pecan.request.application_url
        available = [{'tag': 'v2', 'date': '2013-02-13T00:00:00Z', }]
        collected = [version_descriptor(base_url, v['tag'], v['date'])
                     for v in available]
        versions = {'versions': {'values': collected}}
        return versions


def version_descriptor(base_url, version, released_on):
    url = version_url(base_url, version)
    return {
        'id': version,
        'links': [
            {'href': url, 'rel': 'self', },
            {'href': 'http://docs.openstack.org/',
             'rel': 'describedby', 'type': 'text/html', }],
        'media-types': [
            {'base': 'application/json', 'type': MEDIA_TYPE_JSON % version, },
            {'base': 'application/xml', 'type': MEDIA_TYPE_XML % version, }],
        'status': 'stable',
        'updated': released_on,
    }


def version_url(base_url, version_number):
    return '%s/%s' % (base_url, version_number)
