# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Julien Danjou
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
"""Tests for ceilometer.policy"""

import os
import tempfile

from ceilometer.tests import base
from ceilometer import policy
from ceilometer.openstack.common import cfg


class TestPolicy(base.TestCase):
    def setUp(self):
        super(TestPolicy, self).setUp()
        # Clear cache
        policy._POLICY_PATH = None
        policy._POLICY_CACHE = {}

    def tearDown(self):
        try:
            os.unlink(cfg.CONF.policy_file)
        except OSError:
            pass

    def test_init(self):
        cfg.CONF([])
        cfg.CONF.policy_file = tempfile.mktemp()
        with open(cfg.CONF.policy_file, "w") as f:
            f.write("{}")
        policy.init()

    def test_init_file_not_found(self):
        cfg.CONF([])
        cfg.CONF.policy_file = 'foobar.json.does.not.exist'
        self.assertRaises(cfg.ConfigFilesNotFoundError, policy.init)
