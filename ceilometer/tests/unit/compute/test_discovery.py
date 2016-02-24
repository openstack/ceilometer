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
import datetime

import iso8601
import mock
from oslo_config import fixture as fixture_config
from oslotest import mockpatch

from ceilometer.compute import discovery
import ceilometer.tests.base as base


class TestDiscovery(base.BaseTestCase):

    def setUp(self):
        super(TestDiscovery, self).setUp()

        self.instance = mock.MagicMock()
        self.instance.name = 'instance-00000001'
        setattr(self.instance, 'OS-EXT-SRV-ATTR:instance_name',
                self.instance.name)
        setattr(self.instance, 'OS-EXT-STS:vm_state',
                'active')
        self.instance.id = 1
        self.instance.flavor = {'name': 'm1.small', 'id': 2, 'vcpus': 1,
                                'ram': 512, 'disk': 20, 'ephemeral': 0}
        self.instance.status = 'active'
        self.instance.metadata = {
            'fqdn': 'vm_fqdn',
            'metering.stack': '2cadc4b4-8789-123c-b4eg-edd2f0a9c128',
            'project_cos': 'dev'}

        # as we're having lazy hypervisor inspector singleton object in the
        # base compute pollster class, that leads to the fact that we
        # need to mock all this class property to avoid context sharing between
        # the tests
        self.client = mock.MagicMock()
        self.client.instance_get_all_by_host.return_value = [self.instance]
        patch_client = mockpatch.Patch('ceilometer.nova_client.Client',
                                       return_value=self.client)
        self.useFixture(patch_client)

        self.utc_now = mock.MagicMock(
            return_value=datetime.datetime(2016, 1, 1,
                                           tzinfo=iso8601.iso8601.UTC))
        patch_timeutils = mockpatch.Patch('oslo_utils.timeutils.utcnow',
                                          self.utc_now)
        self.useFixture(patch_timeutils)

        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.CONF.set_override('host', 'test')

    def test_normal_discovery(self):
        dsc = discovery.InstanceDiscovery()
        resources = dsc.discover(mock.MagicMock())

        self.assertEqual(1, len(resources))
        self.assertEqual(1, list(resources)[0].id)

        self.client.instance_get_all_by_host.assert_called_once_with(
            'test', None)

        resources = dsc.discover(mock.MagicMock())
        self.assertEqual(1, len(resources))
        self.assertEqual(1, list(resources)[0].id)
        self.client.instance_get_all_by_host.assert_called_with(
            self.CONF.host, "2016-01-01T00:00:00+00:00")

    def test_discovery_with_resource_update_interval(self):
        self.CONF.set_override("resource_update_interval", 600,
                               group="compute")
        dsc = discovery.InstanceDiscovery()
        dsc.last_run = datetime.datetime(2016, 1, 1,
                                         tzinfo=iso8601.iso8601.UTC)

        self.utc_now.return_value = datetime.datetime(
            2016, 1, 1, minute=5, tzinfo=iso8601.iso8601.UTC)
        resources = dsc.discover(mock.MagicMock())
        self.assertEqual(0, len(resources))
        self.client.instance_get_all_by_host.assert_not_called()

        self.utc_now.return_value = datetime.datetime(
            2016, 1, 1, minute=20, tzinfo=iso8601.iso8601.UTC)
        resources = dsc.discover(mock.MagicMock())
        self.assertEqual(1, len(resources))
        self.assertEqual(1, list(resources)[0].id)
        self.client.instance_get_all_by_host.assert_called_once_with(
            self.CONF.host, "2016-01-01T00:00:00+00:00")
