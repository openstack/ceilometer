# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
#
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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

import mock
import pecan
import wsme

from ceilometer.api.controllers import v2
from ceilometer.openstack.common import test


class TestWsmeCustomType(test.BaseTestCase):
    def setUp(self):
        super(TestWsmeCustomType, self).setUp()
        pecan.response = mock.MagicMock()

    def test_advenum_default(self):
        class dummybase(wsme.types.Base):
            ae = v2.AdvEnum("name", str, "one", "other", default="other")

        obj = dummybase()
        self.assertEqual(obj.ae, "other")

        obj = dummybase(ae="one")
        self.assertEqual(obj.ae, "one")

        self.assertRaises(ValueError, dummybase, ae="not exists")
