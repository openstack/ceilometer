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

from nova import flags
from nova import test

from nova import rpc

from ceilometer import cfg
from ceilometer import storage
from ceilometer.storage import base

# (dhellmann): This is needed to get the fake_rabbit config value set
# up for the test base class.
cfg.CONF.register_opts(rpc.rpc_opts)


class RegisterOpts(test.TestCase):

    def faux_get_engine(self, conf):
        return self._faux_engine

    def test_register_opts(self):
        self.stubs.Set(storage, 'get_engine', self.faux_get_engine)
        flags.FLAGS.metering_storage_engine = 'log'
        self._faux_engine = self.mox.CreateMock(base.StorageEngine)
        self._faux_engine.register_opts(flags.FLAGS)
        self.mox.ReplayAll()
        storage.register_opts(flags.FLAGS)
