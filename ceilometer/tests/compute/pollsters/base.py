#
# Copyright 2012 eNovance <licensing@enovance.com>
# Copyright 2012 Red Hat, Inc
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
from oslotest import mockpatch

import ceilometer.tests.base as base


class TestPollsterBase(base.BaseTestCase):

    def setUp(self):
        super(TestPollsterBase, self).setUp()

        self.inspector = mock.Mock()
        self.instance = mock.MagicMock()
        self.instance.name = 'instance-00000001'
        setattr(self.instance, 'OS-EXT-SRV-ATTR:instance_name',
                self.instance.name)
        self.instance.id = 1
        self.instance.flavor = {'name': 'm1.small', 'id': 2, 'vcpus': 1,
                                'ram': 512, 'disk': 20, 'ephemeral': 0}
        self.instance.status = 'active'

        patch_virt = mockpatch.Patch(
            'ceilometer.compute.virt.inspector.get_hypervisor_inspector',
            new=mock.Mock(return_value=self.inspector))
        self.useFixture(patch_virt)
