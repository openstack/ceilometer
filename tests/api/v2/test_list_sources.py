# -*- encoding: utf-8 -*-
#
# Copyright © 2012 Julien Danjou
#
# Author: Julien Danjou <julien@danjou.info>
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
"""Test listing users.
"""

from .base import FunctionalTest


class TestListSource(FunctionalTest):

    def test_all(self):
        ydata = self.get_json('/sources')
        self.assertEqual(len(ydata), 1)
        source = ydata[0]
        self.assertEqual(source['name'], 'test_source')

    def test_source(self):
        ydata = self.get_json('/sources/test_source')
        self.assert_("data" in ydata)
        self.assert_("somekey" in ydata['data'])
        self.assertEqual(ydata['data']["somekey"], '666')

    def test_unknownsource(self):
        ydata = self.get_json(
            '/sources/test_source_that_does_not_exist',
            expect_errors=True)
        print 'GOT:', ydata
        self.assertEqual(ydata.status_int, 404)
        self.assert_(
            "No source test_source_that_does_not_exist" in
            ydata.json['error_message']
        )
