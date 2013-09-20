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
from ceilometer.tests import base


class TestWsmeCustomType(base.TestCase):
    def setUp(self):
        super(TestWsmeCustomType, self).setUp()
        pecan.response = mock.MagicMock()

    def test_bounded_int_convertion(self):
        bi = v2.BoundedInt(1, 5)
        self.assertEqual(bi.frombasetype("2"), 2)

    def test_bounded_int_invalid_convertion(self):
        bi = v2.BoundedInt(1, 5)
        self.assertRaises(TypeError, bi.frombasetype, wsme)

    def test_bounded_int_maxmin(self):
        bi = v2.BoundedInt(1, 5)
        self.assertRaises(wsme.exc.ClientSideError, bi.validate, -1)
        self.assertRaises(wsme.exc.ClientSideError, bi.validate, 7)
        self.assertEqual(bi.validate(2), 2)

    def test_bounded_int_max(self):
        bi = v2.BoundedInt(max=5)
        self.assertEqual(bi.validate(-1), -1)
        self.assertRaises(wsme.exc.ClientSideError, bi.validate, 7)

    def test_bounded_int_min(self):
        bi = v2.BoundedInt(min=5)
        self.assertEqual(bi.validate(7), 7)
        self.assertRaises(wsme.exc.ClientSideError, bi.validate, -1)

    def test_advenum_default(self):
        class dummybase(wsme.types.Base):
            ae = v2.AdvEnum("name", str, "one", "other", default="other")

        obj = dummybase()
        self.assertEqual(obj.ae, "other")

        obj = dummybase(ae="one")
        self.assertEqual(obj.ae, "one")

        self.assertRaises(ValueError, dummybase, ae="not exists")
