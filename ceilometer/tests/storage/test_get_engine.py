# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Tests for ceilometer/storage/
"""

import mock

from ceilometer.openstack.common import test
from ceilometer import storage
from ceilometer.storage import impl_log


class EngineTest(test.BaseTestCase):

    def test_get_engine(self):
        conf = mock.Mock()
        conf.database.connection = 'log://localhost'
        engine = storage.get_engine(conf)
        self.assertIsInstance(engine, impl_log.LogStorage)

    def test_get_engine_no_such_engine(self):
        conf = mock.Mock()
        conf.database.connection = 'no-such-engine://localhost'
        try:
            storage.get_engine(conf)
        except RuntimeError as err:
            self.assertIn('no-such-engine', unicode(err))
