#
# Copyright 2013 eNovance <licensing@enovance.com>
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
from oslotest import base
import wsme

from ceilometer.api.controllers.v2 import base as v2_base


class TestWsmeCustomType(base.BaseTestCase):

    def test_advenum_default(self):
        class dummybase(wsme.types.Base):
            ae = v2_base.AdvEnum("name", str, "one", "other", default="other")

        obj = dummybase()
        self.assertEqual("other", obj.ae)

        obj = dummybase(ae="one")
        self.assertEqual("one", obj.ae)

        self.assertRaises(wsme.exc.InvalidInput, dummybase, ae="not exists")
