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

import fixtures
import iso8601
import mock
import testtools

try:
    import libvirt
except ImportError:
    libvirt = None

from ceilometer.compute import discovery
from ceilometer.compute.pollsters import util
from ceilometer.compute.virt.libvirt import utils
from ceilometer import service
import ceilometer.tests.base as base


LIBVIRT_METADATA_XML = """
<instance>
  <package version="14.0.0"/>
  <name>test.dom.com</name>
  <creationTime>2016-11-16 07:35:06</creationTime>
  <flavor name="m1.tiny">
    <memory>512</memory>
    <disk>1</disk>
    <swap>0</swap>
    <ephemeral>0</ephemeral>
    <vcpus>1</vcpus>
  </flavor>
  <owner>
    <user uuid="a1f4684e58bd4c88aefd2ecb0783b497">admin</user>
    <project uuid="d99c829753f64057bc0f2030da309943">admin</project>
  </owner>
  <root type="image" uuid="bdaf114a-35e9-4163-accd-226d5944bf11"/>
</instance>
"""

LIBVIRT_DESC_XML = """
<domain type='kvm' id='1'>
  <name>instance-00000001</name>
  <uuid>a75c2fa5-6c03-45a8-bbf7-b993cfcdec27</uuid>
  <os>
    <type arch='x86_64' machine='pc-i440fx-xenial'>hvm</type>
    <kernel>/opt/stack/data/nova/instances/a75c2fa5-6c03-45a8-bbf7-b993cfcdec27/kernel</kernel>
    <initrd>/opt/stack/data/nova/instances/a75c2fa5-6c03-45a8-bbf7-b993cfcdec27/ramdisk</initrd>
    <cmdline>root=/dev/vda console=tty0 console=ttyS0</cmdline>
    <boot dev='hd'/>
    <smbios mode='sysinfo'/>
  </os>
</domain>
"""

LIBVIRT_MANUAL_INSTANCE_DESC_XML = """
<domain type='kvm' id='1'>
  <name>Manual-instance-00000001</name>
  <uuid>5e637d0d-8c0e-441a-a11a-a9dc95aed84e</uuid>
  <os>
    <type arch='x86_64' machine='pc-i440fx-xenial'>hvm</type>
    <kernel>/opt/instances/5e637d0d-8c0e-441a-a11a-a9dc95aed84e/kernel</kernel>
    <initrd>/opt/instances/5e637d0d-8c0e-441a-a11a-a9dc95aed84e/ramdisk</initrd>
    <cmdline>root=/dev/vda console=tty0 console=ttyS0</cmdline>
    <boot dev='hd'/>
    <smbios mode='sysinfo'/>
  </os>
</domain>
"""


class FakeDomain(object):
    def state(self):
        return [1, 2]

    def name(self):
        return "instance-00000001"

    def UUIDString(self):
        return "a75c2fa5-6c03-45a8-bbf7-b993cfcdec27"

    def XMLDesc(self):
        return LIBVIRT_DESC_XML

    def metadata(self, flags, url):
        return LIBVIRT_METADATA_XML


class FakeConn(object):
    def listAllDomains(self):
        return [FakeDomain()]


class FakeManualInstanceDomain(object):
    def state(self):
        return [1, 2]

    def name(self):
        return "Manual-instance-00000001"

    def UUIDString(self):
        return "5e637d0d-8c0e-441a-a11a-a9dc95aed84e"

    def XMLDesc(self):
        return LIBVIRT_MANUAL_INSTANCE_DESC_XML

    def metadata(self, flags, url):
        # Note(xiexianbin): vm not create by nova-compute don't have metadata
        # elements like: '<nova:instance
        #  xmlns:nova="http://openstack.org/xmlns/libvirt/nova/1.0">'
        # When invoke get metadata method, raise libvirtError.
        raise libvirt.libvirtError(
            "metadata not found: Requested metadata element is not present")


class FakeManualInstanceConn(object):
    def listAllDomains(self):
        return [FakeManualInstanceDomain()]


class TestDiscovery(base.BaseTestCase):

    def setUp(self):
        super(TestDiscovery, self).setUp()

        self.instance = mock.MagicMock()
        self.instance.name = 'instance-00000001'
        setattr(self.instance, 'OS-EXT-SRV-ATTR:instance_name',
                self.instance.name)
        setattr(self.instance, 'OS-EXT-STS:vm_state',
                'active')
        # FIXME(sileht): This is wrong, this should be a uuid
        # The internal id of nova can't be retrieved via API or notification
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
        patch_client = fixtures.MockPatch('ceilometer.nova_client.Client',
                                          return_value=self.client)
        self.useFixture(patch_client)

        self.utc_now = mock.MagicMock(
            return_value=datetime.datetime(2016, 1, 1,
                                           tzinfo=iso8601.iso8601.UTC))
        patch_timeutils = fixtures.MockPatch('oslo_utils.timeutils.utcnow',
                                             self.utc_now)
        self.useFixture(patch_timeutils)

        self.CONF = service.prepare_service([], [])
        self.CONF.set_override('host', 'test')

    def test_normal_discovery(self):
        self.CONF.set_override("instance_discovery_method",
                               "naive",
                               group="compute")
        dsc = discovery.InstanceDiscovery(self.CONF)
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
        self.CONF.set_override("instance_discovery_method",
                               "naive",
                               group="compute")
        self.CONF.set_override("resource_update_interval", 600,
                               group="compute")
        dsc = discovery.InstanceDiscovery(self.CONF)
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

    @mock.patch.object(utils, "libvirt")
    @mock.patch.object(discovery, "libvirt")
    def test_discovery_with_libvirt(self, libvirt, libvirt2):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        libvirt.VIR_DOMAIN_METADATA_ELEMENT = 2
        libvirt2.openReadOnly.return_value = FakeConn()
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())

        self.assertEqual(1, len(resources))
        r = list(resources)[0]
        s = util.make_sample_from_instance(self.CONF, r, "metric", "delta",
                                           "carrot", 1)
        self.assertEqual("a75c2fa5-6c03-45a8-bbf7-b993cfcdec27",
                         s.resource_id)
        self.assertEqual("d99c829753f64057bc0f2030da309943",
                         s.project_id)
        self.assertEqual("a1f4684e58bd4c88aefd2ecb0783b497",
                         s.user_id)

        metadata = s.resource_metadata
        self.assertEqual(1, metadata["vcpus"])
        self.assertEqual(512, metadata["memory_mb"])
        self.assertEqual(1, metadata["disk_gb"])
        self.assertEqual(0, metadata["ephemeral_gb"])
        self.assertEqual(1, metadata["root_gb"])
        self.assertEqual("bdaf114a-35e9-4163-accd-226d5944bf11",
                         metadata["image_ref"])
        self.assertEqual("test.dom.com", metadata["display_name"])
        self.assertEqual("instance-00000001", metadata["name"])
        self.assertEqual("a75c2fa5-6c03-45a8-bbf7-b993cfcdec27",
                         metadata["instance_id"])
        self.assertEqual("m1.tiny", metadata["instance_type"])
        self.assertEqual(
            "4d0bc931ea7f0513da2efd9acb4cf3a273c64b7bcc544e15c070e662",
            metadata["host"])
        self.assertEqual(self.CONF.host, metadata["instance_host"])
        self.assertEqual("active", metadata["status"])
        self.assertEqual("running", metadata["state"])
        self.assertEqual("hvm", metadata["os_type"])
        self.assertEqual("x86_64", metadata["architecture"])

    def test_discovery_with_legacy_resource_cache_cleanup(self):
        self.CONF.set_override("instance_discovery_method", "naive",
                               group="compute")
        self.CONF.set_override("resource_update_interval", 600,
                               group="compute")
        self.CONF.set_override("resource_cache_expiry", 1800,
                               group="compute")
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())
        self.assertEqual(1, len(resources))

        self.utc_now.return_value = datetime.datetime(
            2016, 1, 1, minute=20, tzinfo=iso8601.iso8601.UTC)
        resources = dsc.discover(mock.MagicMock())
        self.assertEqual(1, len(resources))

        self.utc_now.return_value = datetime.datetime(
            2016, 1, 1, minute=31, tzinfo=iso8601.iso8601.UTC)
        resources = dsc.discover(mock.MagicMock())
        self.assertEqual(1, len(resources))

        expected_calls = [mock.call('test', None),
                          mock.call('test', '2016-01-01T00:00:00+00:00'),
                          mock.call('test', None)]
        self.assertEqual(expected_calls,
                         self.client.instance_get_all_by_host.call_args_list)

    @testtools.skipUnless(libvirt, "libvirt not available")
    @mock.patch.object(utils, "libvirt")
    @mock.patch.object(discovery, "libvirt")
    def test_discovery_with_libvirt_error(self, libvirt, libvirt2):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        libvirt.VIR_DOMAIN_METADATA_ELEMENT = 2
        libvirt2.openReadOnly.return_value = FakeManualInstanceConn()
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())
        self.assertEqual(0, len(resources))
