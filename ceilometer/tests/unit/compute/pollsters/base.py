#
# Copyright 2012 eNovance <licensing@enovance.com>
# Copyright 2012 Red Hat, Inc
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

import fixtures
import mock

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer import service
import ceilometer.tests.base as base


class TestPollsterBase(base.BaseTestCase):

    def setUp(self):
        super(TestPollsterBase, self).setUp()
        self.CONF = service.prepare_service([], [])

        self.inspector = mock.Mock()
        self.instance = mock.MagicMock()
        self.instance.name = 'instance-00000001'
        setattr(self.instance, 'OS-EXT-SRV-ATTR:instance_name',
                self.instance.name)
        setattr(self.instance, 'OS-EXT-STS:vm_state',
                'active')
        setattr(self.instance, 'OS-EXT-STS:task_state', None)
        self.instance.id = 1
        self.instance.flavor = {'name': 'm1.small', 'id': 2, 'vcpus': 1,
                                'ram': 512, 'disk': 20, 'ephemeral': 0}
        self.instance.status = 'active'
        self.instance.metadata = {
            'fqdn': 'vm_fqdn',
            'metering.stack': '2cadc4b4-8789-123c-b4eg-edd2f0a9c128',
            'project_cos': 'dev'}

        self.useFixture(fixtures.MockPatch(
            'ceilometer.compute.virt.inspector.get_hypervisor_inspector',
            new=mock.Mock(return_value=self.inspector)))

        # as we're having lazy hypervisor inspector singleton object in the
        # base compute pollster class, that leads to the fact that we
        # need to mock all this class property to avoid context sharing between
        # the tests
        self.useFixture(fixtures.MockPatch(
            'ceilometer.compute.pollsters.'
            'GenericComputePollster._get_inspector',
            return_value=self.inspector))

    def _mock_inspect_instance(self, *data):
        next_value = iter(data)

        def inspect(instance, duration):
            value = next(next_value)
            if isinstance(value, virt_inspector.InstanceStats):
                return value
            else:
                raise value

        self.inspector.inspect_instance = mock.Mock(side_effect=inspect)
