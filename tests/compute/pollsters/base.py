# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
# Copyright © 2012 Red Hat, Inc
#
# Author: Julien Danjou <julien@danjou.info>
# Author: Eoghan Glynn <eglynn@redhat.com>
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

from ceilometer.openstack.common import test
from ceilometer.openstack.common.fixture import moxstubout
from ceilometer.compute.virt import inspector as virt_inspector


class TestPollsterBase(test.BaseTestCase):

    def setUp(self):
        super(TestPollsterBase, self).setUp()
        self.mox = self.useFixture(moxstubout.MoxStubout()).mox
        self.mox.StubOutWithMock(virt_inspector, 'get_hypervisor_inspector')
        self.inspector = self.mox.CreateMock(virt_inspector.Inspector)
        virt_inspector.get_hypervisor_inspector().AndReturn(self.inspector)
        self.instance = mock.MagicMock()
        self.instance.name = 'instance-00000001'
        setattr(self.instance, 'OS-EXT-SRV-ATTR:instance_name',
                self.instance.name)
        self.instance.id = 1
        self.instance.flavor = {'name': 'm1.small', 'id': 2, 'vcpus': 1,
                                'ram': 512, 'disk': 20, 'ephemeral': 0}
