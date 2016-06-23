#
# Copyright Ericsson AB 2014. All rights reserved
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
from ceilometer.tests.functional.api import v2 as tests_api


class TestCapabilitiesController(tests_api.FunctionalTest):

    def setUp(self):
            super(TestCapabilitiesController, self).setUp()
            self.url = '/capabilities'

    def test_capabilities(self):
        data = self.get_json(self.url)
        # check that capabilities data contains both 'api' and 'storage' fields
        self.assertIsNotNone(data)
        self.assertNotEqual({}, data)
        self.assertIn('api', data)
        self.assertIn('storage', data)
