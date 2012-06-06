#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
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

import unittest
import logging

from ceilometer import log
from ceilometer import cfg

class LoggerTestCase(unittest.TestCase):
    def setUp(self):
        super(LoggerTestCase, self).setUp()
        self.log = log.getLogger()

    def test_log_level(self):
        cfg.CONF.log_level = "info"
        log.setup()
        self.assertEqual(logging.INFO, self.log.getEffectiveLevel())

    def test_child_log_level(self):
        cfg.CONF.log_level = "info"
        log.setup()
        self.assertEqual(logging.INFO, log.getLogger('ceilometer.foobar').getEffectiveLevel())


class LogfilePathTestCase(unittest.TestCase):
    def test_log_path_logdir(self):
        cfg.CONF.log_dir = '/some/path'
        cfg.CONF.log_file = None
        self.assertEquals(log._get_log_file_path(binary='foo-bar'),
                          '/some/path/foo-bar.log')

    def test_log_path_logfile(self):
        cfg.CONF.log_file = '/some/path/foo-bar.log'
        self.assertEquals(log._get_log_file_path(binary='foo-bar'),
                          '/some/path/foo-bar.log')

    def test_log_path_none(self):
        cfg.CONF.log_dir = None
        cfg.CONF.log_file = None
        self.assertTrue(log._get_log_file_path(binary='foo-bar') is None)

    def test_log_path_logfile_overrides_logdir(self):
        cfg.CONF.log_dir = '/some/other/path'
        cfg.CONF.log_file = '/some/path/foo-bar.log'
        self.assertEquals(log._get_log_file_path(binary='foo-bar'),
                          '/some/path/foo-bar.log')

