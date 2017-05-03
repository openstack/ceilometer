#
# Copyright 2016 Mirantis, Inc
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

import fixtures
import mock

from ceilometer import declarative
from ceilometer.tests import base


class TestDefinition(base.BaseTestCase):

    def setUp(self):
        super(TestDefinition, self).setUp()
        self.configs = [
            "_field1",
            "_field2|_field3",
            {'fields': 'field4.`split(., 1, 1)`'},
            {'fields': ['field5.arg', 'field6'], 'type': 'text'}
        ]
        self.parser = mock.MagicMock()
        parser_patch = fixtures.MockPatch(
            "jsonpath_rw_ext.parser.ExtentedJsonPathParser.parse",
            new=self.parser)
        self.useFixture(parser_patch)

    def test_caching_parsers(self):
        for config in self.configs * 2:
            declarative.Definition("test", config, mock.MagicMock())
        self.assertEqual(4, self.parser.call_count)
        self.parser.assert_has_calls([
            mock.call("_field1"),
            mock.call("_field2|_field3"),
            mock.call("field4.`split(., 1, 1)`"),
            mock.call("(field5.arg)|(field6)"),
        ])
