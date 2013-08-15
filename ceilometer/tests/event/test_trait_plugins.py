# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Rackspace Hosting.
#
# Author: Monsyne Dragon <mdragon@rackspace.com>
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

from ceilometer.event import trait_plugins
from ceilometer.openstack.common import test


class TestSplitterPlugin(test.BaseTestCase):

    def setUp(self):
        super(TestSplitterPlugin, self).setUp()
        self.pclass = trait_plugins.SplitterTraitPlugin

    def test_split(self):
        param = dict(separator='-', segment=0)
        plugin = self.pclass(**param)
        match_list = [('test.thing', 'test-foobar-baz')]
        value = plugin.trait_value(match_list)
        self.assertEqual(value, 'test')

        param = dict(separator='-', segment=1)
        plugin = self.pclass(**param)
        match_list = [('test.thing', 'test-foobar-baz')]
        value = plugin.trait_value(match_list)
        self.assertEqual(value, 'foobar')

        param = dict(separator='-', segment=1, max_split=1)
        plugin = self.pclass(**param)
        match_list = [('test.thing', 'test-foobar-baz')]
        value = plugin.trait_value(match_list)
        self.assertEqual(value, 'foobar-baz')

    def test_no_sep(self):
        param = dict(separator='-', segment=0)
        plugin = self.pclass(**param)
        match_list = [('test.thing', 'test.foobar.baz')]
        value = plugin.trait_value(match_list)
        self.assertEqual(value, 'test.foobar.baz')

    def test_no_segment(self):
        param = dict(separator='-', segment=5)
        plugin = self.pclass(**param)
        match_list = [('test.thing', 'test-foobar-baz')]
        value = plugin.trait_value(match_list)
        self.assertIs(None, value)

    def test_no_match(self):
        param = dict(separator='-', segment=0)
        plugin = self.pclass(**param)
        match_list = []
        value = plugin.trait_value(match_list)
        self.assertIs(None, value)


class TestBitfieldPlugin(test.BaseTestCase):

    def setUp(self):
        super(TestBitfieldPlugin, self).setUp()
        self.pclass = trait_plugins.BitfieldTraitPlugin
        self.init = 0
        self.params = dict(initial_bitfield=self.init,
                           flags=[dict(path='payload.foo', bit=0, value=42),
                                  dict(path='payload.foo', bit=1, value=12),
                                  dict(path='payload.thud', bit=1, value=23),
                                  dict(path='thingy.boink', bit=4),
                                  dict(path='thingy.quux', bit=6,
                                       value="wokka"),
                                  dict(path='payload.bar', bit=10,
                                       value='test')])

    def test_bitfield(self):
        match_list = [('payload.foo', 12),
                      ('payload.bar', 'test'),
                      ('thingy.boink', 'testagain')]

        plugin = self.pclass(**self.params)
        value = plugin.trait_value(match_list)
        self.assertEqual(value, 0x412)

    def test_initial(self):
        match_list = [('payload.foo', 12),
                      ('payload.bar', 'test'),
                      ('thingy.boink', 'testagain')]
        self.params['initial_bitfield'] = 0x2000
        plugin = self.pclass(**self.params)
        value = plugin.trait_value(match_list)
        self.assertEqual(value, 0x2412)

    def test_no_match(self):
        match_list = []
        plugin = self.pclass(**self.params)
        value = plugin.trait_value(match_list)
        self.assertEqual(value, self.init)

    def test_multi(self):
        match_list = [('payload.foo', 12),
                      ('payload.thud', 23),
                      ('payload.bar', 'test'),
                      ('thingy.boink', 'testagain')]

        plugin = self.pclass(**self.params)
        value = plugin.trait_value(match_list)
        self.assertEqual(value, 0x412)
