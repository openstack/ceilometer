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

import argparse
import datetime
from unittest import mock

import fixtures
import libvirt
from novaclient import exceptions

from ceilometer.compute import discovery
from ceilometer.compute.pollsters import util
from ceilometer import service
from ceilometer.tests import base


LIBVIRT_METADATA_XML = """
<instance>
  <package version="14.0.0"/>
  <name>test.dom.com</name>
  <creationTime>2016-11-16 07:35:06</creationTime>
  <flavor name="m1.tiny" id="eba4213d-3c6c-4b5f-8158-dd0022d71d62">
    <memory>512</memory>
    <disk>1</disk>
    <swap>0</swap>
    <ephemeral>0</ephemeral>
    <vcpus>1</vcpus>
    <extraSpecs>
      <extraSpec name="hw_rng:allowed">true</extraSpec>
    </extraSpecs>
  </flavor>
  <image uuid="bdaf114a-35e9-4163-accd-226d5944bf11">
    <containerFormat>bare</containerFormat>
    <diskFormat>raw</diskFormat>
    <minDisk>1</minDisk>
    <minRam>0</minRam>
    <properties>
      <property name="os_distro">ubuntu</property>
      <property name="os_type">linux</property>
    </properties>
  </image>
  <owner>
    <user uuid="a1f4684e58bd4c88aefd2ecb0783b497">admin</user>
    <project uuid="d99c829753f64057bc0f2030da309943">admin</project>
  </owner>
  <root type="image" uuid="bdaf114a-35e9-4163-accd-226d5944bf11"/>
</instance>
"""

LIBVIRT_METADATA_XML_OLD = """
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

LIBVIRT_METADATA_XML_EMPTY_FLAVOR_ID = """
<instance>
  <package version="14.0.0"/>
  <name>test.dom.com</name>
  <creationTime>2016-11-16 07:35:06</creationTime>
  <flavor name="m1.tiny" id="">
    <memory>512</memory>
    <disk>1</disk>
    <swap>0</swap>
    <ephemeral>0</ephemeral>
    <vcpus>1</vcpus>
    <extraSpecs>
      <extraSpec name="hw_rng:allowed">true</extraSpec>
    </extraSpecs>
  </flavor>
  <owner>
    <user uuid="a1f4684e58bd4c88aefd2ecb0783b497">admin</user>
    <project uuid="d99c829753f64057bc0f2030da309943">admin</project>
  </owner>
  <root type="image" uuid="bdaf114a-35e9-4163-accd-226d5944bf11"/>
</instance>
"""

LIBVIRT_METADATA_XML_NO_FLAVOR_ID = """
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
    <extraSpecs>
      <extraSpec name="hw_rng:allowed">true</extraSpec>
    </extraSpecs>
  </flavor>
  <owner>
    <user uuid="a1f4684e58bd4c88aefd2ecb0783b497">admin</user>
    <project uuid="d99c829753f64057bc0f2030da309943">admin</project>
  </owner>
  <root type="image" uuid="bdaf114a-35e9-4163-accd-226d5944bf11"/>
</instance>
"""

LIBVIRT_METADATA_XML_EMPTY_FLAVOR_EXTRA_SPECS = """
<instance>
  <package version="14.0.0"/>
  <name>test.dom.com</name>
  <creationTime>2016-11-16 07:35:06</creationTime>
  <flavor name="m1.tiny" id="eba4213d-3c6c-4b5f-8158-dd0022d71d62">
    <memory>512</memory>
    <disk>1</disk>
    <swap>0</swap>
    <ephemeral>0</ephemeral>
    <vcpus>1</vcpus>
    <extraSpecs></extraSpecs>
  </flavor>
  <owner>
    <user uuid="a1f4684e58bd4c88aefd2ecb0783b497">admin</user>
    <project uuid="d99c829753f64057bc0f2030da309943">admin</project>
  </owner>
  <root type="image" uuid="bdaf114a-35e9-4163-accd-226d5944bf11"/>
</instance>
"""

LIBVIRT_METADATA_XML_NO_FLAVOR_EXTRA_SPECS = """
<instance>
  <package version="14.0.0"/>
  <name>test.dom.com</name>
  <creationTime>2016-11-16 07:35:06</creationTime>
  <flavor name="m1.tiny" id="eba4213d-3c6c-4b5f-8158-dd0022d71d62">
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

LIBVIRT_METADATA_XML_FROM_VOLUME_IMAGE = """
<instance>
  <package version="14.0.0"/>
  <name>test.dom.com</name>
  <creationTime>2016-11-16 07:35:06</creationTime>
  <flavor name="m1.tiny" id="eba4213d-3c6c-4b5f-8158-dd0022d71d62">
    <memory>512</memory>
    <disk>1</disk>
    <swap>0</swap>
    <ephemeral>0</ephemeral>
    <vcpus>1</vcpus>
    <extraSpecs>
      <extraSpec name="hw_rng:allowed">true</extraSpec>
    </extraSpecs>
  </flavor>
  <image uuid="">
    <containerFormat>bare</containerFormat>
    <diskFormat>raw</diskFormat>
    <minDisk>1</minDisk>
    <minRam>0</minRam>
    <properties>
      <property name="os_distro">ubuntu</property>
      <property name="os_type">linux</property>
    </properties>
  </image>
  <owner>
    <user uuid="a1f4684e58bd4c88aefd2ecb0783b497">admin</user>
    <project uuid="d99c829753f64057bc0f2030da309943">admin</project>
  </owner>
</instance>
"""

LIBVIRT_METADATA_XML_FROM_VOLUME_NO_IMAGE = """
<instance>
  <package version="14.0.0"/>
  <name>test.dom.com</name>
  <creationTime>2016-11-16 07:35:06</creationTime>
  <flavor name="m1.tiny" id="eba4213d-3c6c-4b5f-8158-dd0022d71d62">
    <memory>512</memory>
    <disk>1</disk>
    <swap>0</swap>
    <ephemeral>0</ephemeral>
    <vcpus>1</vcpus>
    <extraSpecs>
      <extraSpec name="hw_rng:allowed">true</extraSpec>
    </extraSpecs>
  </flavor>
  <image uuid="">
    <properties></properties>
  </image>
  <owner>
    <user uuid="a1f4684e58bd4c88aefd2ecb0783b497">admin</user>
    <project uuid="d99c829753f64057bc0f2030da309943">admin</project>
  </owner>
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


class FakeDomain:
    def __init__(self, desc=None, metadata=None):
        self._desc = desc or LIBVIRT_DESC_XML
        self._metadata = metadata or LIBVIRT_METADATA_XML

    def state(self):
        return [1, 2]

    def name(self):
        return "instance-00000001"

    def UUIDString(self):
        return "a75c2fa5-6c03-45a8-bbf7-b993cfcdec27"

    def XMLDesc(self):
        return self._desc

    def metadata(self, flags, url):
        return self._metadata


class FakeConn:
    def __init__(self, domains=None):
        self._domains = domains or [FakeDomain()]

    def listAllDomains(self):
        return list(self._domains)

    def isAlive(self):
        return True


class FakeManualInstanceDomain:
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
        e = libvirt.libvirtError(
            "metadata not found: Requested metadata element is not present")

        def fake_error_code(*args, **kwargs):
            return libvirt.VIR_ERR_NO_DOMAIN_METADATA

        e.get_error_code = fake_error_code
        raise e


class FakeManualInstanceConn:
    def listAllDomains(self):
        return [FakeManualInstanceDomain()]

    def isAlive(self):
        return True


class TestDiscovery(base.BaseTestCase):

    def setUp(self):
        super().setUp()

        self.instance = mock.MagicMock()
        self.instance.name = 'instance-00000001'
        setattr(self.instance, 'OS-EXT-SRV-ATTR:instance_name',
                self.instance.name)
        setattr(self.instance, 'OS-EXT-STS:vm_state',
                'active')
        # FIXME(sileht): This is wrong, this should be a uuid
        # The internal id of nova can't be retrieved via API or notification
        self.instance.id = 1
        self.instance.flavor = {'name': 'm1.small',
                                'id': 'eba4213d-3c6c-4b5f-8158-dd0022d71d62',
                                'vcpus': 1,
                                'ram': 512,
                                'disk': 20,
                                'ephemeral': 0,
                                'extra_specs': {'hw_rng:allowed': 'true'}}
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
            return_value=datetime.datetime(
                2016, 1, 1, tzinfo=datetime.timezone.utc))
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
        dsc.last_run = datetime.datetime(
            2016, 1, 1, tzinfo=datetime.timezone.utc)

        self.utc_now.return_value = datetime.datetime(
            2016, 1, 1, minute=5, tzinfo=datetime.timezone.utc)
        resources = dsc.discover(mock.MagicMock())
        self.assertEqual(0, len(resources))
        self.client.instance_get_all_by_host.assert_not_called()

        self.utc_now.return_value = datetime.datetime(
            2016, 1, 1, minute=20, tzinfo=datetime.timezone.utc)
        resources = dsc.discover(mock.MagicMock())
        self.assertEqual(1, len(resources))
        self.assertEqual(1, list(resources)[0].id)
        self.client.instance_get_all_by_host.assert_called_once_with(
            self.CONF.host, "2016-01-01T00:00:00+00:00")

    @mock.patch.object(discovery.InstanceDiscovery, "get_server")
    @mock.patch.object(discovery.InstanceDiscovery, "get_flavor_id")
    @mock.patch("ceilometer.compute.virt.libvirt.utils."
                "refresh_libvirt_connection")
    def test_discovery_with_libvirt(
            self, mock_libvirt_conn,
            mock_get_flavor_id, mock_get_server):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        mock_libvirt_conn.return_value = FakeConn()
        mock_get_server.return_value = argparse.Namespace(
            metadata={"metering.server_group": "group1"})
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())

        mock_get_flavor_id.assert_not_called()
        mock_get_server.assert_called_with(
            "a75c2fa5-6c03-45a8-bbf7-b993cfcdec27")

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
        self.assertEqual({"name": "m1.tiny",
                          "id": "eba4213d-3c6c-4b5f-8158-dd0022d71d62",
                          "ram": 512,
                          "disk": 1,
                          "swap": 0,
                          "ephemeral": 0,
                          "vcpus": 1,
                          "extra_specs": {"hw_rng:allowed": "true"}},
                         metadata["flavor"])
        self.assertEqual(
            "4d0bc931ea7f0513da2efd9acb4cf3a273c64b7bcc544e15c070e662",
            metadata["host"])
        self.assertEqual(self.CONF.host, metadata["instance_host"])
        self.assertEqual("active", metadata["status"])
        self.assertEqual("running", metadata["state"])
        self.assertEqual("hvm", metadata["os_type"])
        self.assertEqual("x86_64", metadata["architecture"])
        self.assertEqual({"server_group": "group1"},
                         metadata["user_metadata"])
        self.assertEqual({"id"},
                         set(metadata["image"].keys()))
        self.assertEqual("bdaf114a-35e9-4163-accd-226d5944bf11",
                         metadata["image"]["id"])
        self.assertIn("image_meta", metadata)
        self.assertEqual({"base_image_ref",
                          "container_format",
                          "disk_format",
                          "min_disk",
                          "min_ram",
                          "os_distro",
                          "os_type"},
                         set(metadata["image_meta"].keys()))
        self.assertEqual("bdaf114a-35e9-4163-accd-226d5944bf11",
                         metadata["image_meta"]["base_image_ref"])
        self.assertEqual("bare",
                         metadata["image_meta"]["container_format"])
        self.assertEqual("raw",
                         metadata["image_meta"]["disk_format"])
        self.assertEqual("1",
                         metadata["image_meta"]["min_disk"])
        self.assertEqual("0",
                         metadata["image_meta"]["min_ram"])
        self.assertEqual("ubuntu",
                         metadata["image_meta"]["os_distro"])
        self.assertEqual("linux",
                         metadata["image_meta"]["os_type"])

    @mock.patch.object(discovery.InstanceDiscovery, "get_server")
    @mock.patch.object(discovery.InstanceDiscovery, "get_flavor_id")
    @mock.patch("ceilometer.compute.virt.libvirt.utils."
                "refresh_libvirt_connection")
    def test_discovery_with_libvirt_old(
            self, mock_libvirt_conn,
            mock_get_flavor_id, mock_get_server):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        mock_libvirt_conn.return_value = FakeConn(
            domains=[FakeDomain(metadata=LIBVIRT_METADATA_XML_OLD)])
        mock_get_server.return_value = argparse.Namespace(
            flavor={"id": "eba4213d-3c6c-4b5f-8158-dd0022d71d62"},
            metadata={"metering.server_group": "group1"})
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())

        mock_get_flavor_id.assert_not_called()
        mock_get_server.assert_called_with(
            "a75c2fa5-6c03-45a8-bbf7-b993cfcdec27")

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
        self.assertEqual({"name": "m1.tiny",
                          "id": "eba4213d-3c6c-4b5f-8158-dd0022d71d62",
                          "ram": 512,
                          "disk": 1,
                          "swap": 0,
                          "ephemeral": 0,
                          "vcpus": 1},
                         metadata["flavor"])
        self.assertEqual(
            "4d0bc931ea7f0513da2efd9acb4cf3a273c64b7bcc544e15c070e662",
            metadata["host"])
        self.assertEqual(self.CONF.host, metadata["instance_host"])
        self.assertEqual("active", metadata["status"])
        self.assertEqual("running", metadata["state"])
        self.assertEqual("hvm", metadata["os_type"])
        self.assertEqual("x86_64", metadata["architecture"])
        self.assertEqual({"server_group": "group1"},
                         metadata["user_metadata"])
        self.assertEqual({"id"},
                         set(metadata["image"].keys()))
        self.assertEqual("bdaf114a-35e9-4163-accd-226d5944bf11",
                         metadata["image"]["id"])
        self.assertNotIn("image_meta", metadata)

    @mock.patch.object(discovery.InstanceDiscovery, "get_server")
    @mock.patch.object(discovery.InstanceDiscovery, "get_flavor_id")
    @mock.patch("ceilometer.compute.virt.libvirt.utils."
                "refresh_libvirt_connection")
    def test_discovery_with_libvirt_no_extra_metadata(
            self, mock_libvirt_conn,
            mock_get_flavor_id, mock_get_server):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        self.CONF.set_override("fetch_extra_metadata", False, group="compute")
        mock_libvirt_conn.return_value = FakeConn()
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())

        mock_get_flavor_id.assert_not_called()
        mock_get_server.assert_not_called()

        self.assertEqual(1, len(resources))
        r = list(resources)[0]
        s = util.make_sample_from_instance(self.CONF, r, "metric", "delta",
                                           "carrot", 1)

        metadata = s.resource_metadata
        self.assertNotIn("user_metadata", metadata)

    @mock.patch.object(discovery.InstanceDiscovery, "get_server")
    @mock.patch.object(discovery.InstanceDiscovery, "get_flavor_id")
    @mock.patch("ceilometer.compute.virt.libvirt.utils."
                "refresh_libvirt_connection")
    def test_discovery_with_libvirt_empty_flavor_id_get_by_flavor(
            self, mock_libvirt_conn,
            mock_get_flavor_id, mock_get_server):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        self.CONF.set_override("fetch_extra_metadata", False, group="compute")
        mock_libvirt_conn.return_value = FakeConn(
            domains=[FakeDomain(
                metadata=LIBVIRT_METADATA_XML_EMPTY_FLAVOR_ID)])
        mock_get_flavor_id.return_value = (
            "eba4213d-3c6c-4b5f-8158-dd0022d71d62")
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())

        mock_get_flavor_id.assert_called_with("m1.tiny")
        mock_get_server.assert_not_called()

        self.assertEqual(1, len(resources))
        r = list(resources)[0]
        s = util.make_sample_from_instance(self.CONF, r, "metric", "delta",
                                           "carrot", 1)

        metadata = s.resource_metadata
        self.assertEqual("m1.tiny", metadata["instance_type"])
        self.assertEqual({"name": "m1.tiny",
                          "id": "eba4213d-3c6c-4b5f-8158-dd0022d71d62",
                          "ram": 512,
                          "disk": 1,
                          "swap": 0,
                          "ephemeral": 0,
                          "vcpus": 1,
                          "extra_specs": {"hw_rng:allowed": "true"}},
                         metadata["flavor"])

    @mock.patch.object(discovery.InstanceDiscovery, "get_server")
    @mock.patch.object(discovery.InstanceDiscovery, "get_flavor_id")
    @mock.patch("ceilometer.compute.virt.libvirt.utils."
                "refresh_libvirt_connection")
    def test_discovery_with_libvirt_empty_flavor_id_get_by_server(
            self, mock_libvirt_conn,
            mock_get_flavor_id, mock_get_server):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        self.CONF.set_override("fetch_extra_metadata", True, group="compute")
        mock_libvirt_conn.return_value = FakeConn(
            domains=[FakeDomain(
                metadata=LIBVIRT_METADATA_XML_EMPTY_FLAVOR_ID)])
        mock_get_server.return_value = argparse.Namespace(
            flavor={"id": "eba4213d-3c6c-4b5f-8158-dd0022d71d62"},
            metadata={})
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())

        mock_get_flavor_id.assert_not_called()
        mock_get_server.assert_called_with(
            "a75c2fa5-6c03-45a8-bbf7-b993cfcdec27")

        self.assertEqual(1, len(resources))
        r = list(resources)[0]
        s = util.make_sample_from_instance(self.CONF, r, "metric", "delta",
                                           "carrot", 1)

        metadata = s.resource_metadata
        self.assertEqual("m1.tiny", metadata["instance_type"])
        self.assertEqual({"name": "m1.tiny",
                          "id": "eba4213d-3c6c-4b5f-8158-dd0022d71d62",
                          "ram": 512,
                          "disk": 1,
                          "swap": 0,
                          "ephemeral": 0,
                          "vcpus": 1,
                          "extra_specs": {"hw_rng:allowed": "true"}},
                         metadata["flavor"])

    @mock.patch.object(discovery.InstanceDiscovery, "get_server")
    @mock.patch.object(discovery.InstanceDiscovery, "get_flavor_id")
    @mock.patch("ceilometer.compute.virt.libvirt.utils."
                "refresh_libvirt_connection")
    def test_discovery_with_libvirt_no_flavor_id_get_by_flavor(
            self, mock_libvirt_conn,
            mock_get_flavor_id, mock_get_server):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        self.CONF.set_override("fetch_extra_metadata", False, group="compute")
        mock_libvirt_conn.return_value = FakeConn(
            domains=[FakeDomain(metadata=LIBVIRT_METADATA_XML_NO_FLAVOR_ID)])
        mock_get_flavor_id.return_value = (
            "eba4213d-3c6c-4b5f-8158-dd0022d71d62")
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())

        mock_get_flavor_id.assert_called_with("m1.tiny")
        mock_get_server.assert_not_called()

        self.assertEqual(1, len(resources))
        r = list(resources)[0]
        s = util.make_sample_from_instance(self.CONF, r, "metric", "delta",
                                           "carrot", 1)

        metadata = s.resource_metadata
        self.assertEqual("m1.tiny", metadata["instance_type"])
        self.assertEqual({"name": "m1.tiny",
                          "id": "eba4213d-3c6c-4b5f-8158-dd0022d71d62",
                          "ram": 512,
                          "disk": 1,
                          "swap": 0,
                          "ephemeral": 0,
                          "vcpus": 1,
                          "extra_specs": {"hw_rng:allowed": "true"}},
                         metadata["flavor"])

    @mock.patch.object(discovery.InstanceDiscovery, "get_server")
    @mock.patch.object(discovery.InstanceDiscovery, "get_flavor_id")
    @mock.patch("ceilometer.compute.virt.libvirt.utils."
                "refresh_libvirt_connection")
    def test_discovery_with_libvirt_no_flavor_id_get_by_server(
            self, mock_libvirt_conn,
            mock_get_flavor_id, mock_get_server):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        self.CONF.set_override("fetch_extra_metadata", True, group="compute")
        mock_libvirt_conn.return_value = FakeConn(
            domains=[FakeDomain(metadata=LIBVIRT_METADATA_XML_NO_FLAVOR_ID)])
        mock_get_server.return_value = argparse.Namespace(
            flavor={"id": "eba4213d-3c6c-4b5f-8158-dd0022d71d62"},
            metadata={})
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())

        mock_get_flavor_id.assert_not_called()
        mock_get_server.assert_called_with(
            "a75c2fa5-6c03-45a8-bbf7-b993cfcdec27")

        self.assertEqual(1, len(resources))
        r = list(resources)[0]
        s = util.make_sample_from_instance(self.CONF, r, "metric", "delta",
                                           "carrot", 1)

        metadata = s.resource_metadata
        self.assertEqual("m1.tiny", metadata["instance_type"])
        self.assertEqual({"name": "m1.tiny",
                          "id": "eba4213d-3c6c-4b5f-8158-dd0022d71d62",
                          "ram": 512,
                          "disk": 1,
                          "swap": 0,
                          "ephemeral": 0,
                          "vcpus": 1,
                          "extra_specs": {"hw_rng:allowed": "true"}},
                         metadata["flavor"])

    @mock.patch.object(discovery.InstanceDiscovery, "get_server")
    @mock.patch.object(discovery.InstanceDiscovery, "get_flavor_id")
    @mock.patch("ceilometer.compute.virt.libvirt.utils."
                "refresh_libvirt_connection")
    def test_discovery_with_libvirt_empty_flavor_extra_specs(
            self, mock_libvirt_conn,
            mock_get_flavor_id, mock_get_server):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        self.CONF.set_override("fetch_extra_metadata", False, group="compute")
        mock_libvirt_conn.return_value = FakeConn(
            domains=[FakeDomain(
                metadata=LIBVIRT_METADATA_XML_EMPTY_FLAVOR_EXTRA_SPECS)])
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())

        mock_get_flavor_id.assert_not_called()
        mock_get_server.assert_not_called()

        self.assertEqual(1, len(resources))
        r = list(resources)[0]
        s = util.make_sample_from_instance(self.CONF, r, "metric", "delta",
                                           "carrot", 1)

        metadata = s.resource_metadata
        self.assertEqual("m1.tiny", metadata["instance_type"])
        self.assertEqual({"name": "m1.tiny",
                          "id": "eba4213d-3c6c-4b5f-8158-dd0022d71d62",
                          "ram": 512,
                          "disk": 1,
                          "swap": 0,
                          "ephemeral": 0,
                          "vcpus": 1,
                          "extra_specs": {}},
                         metadata["flavor"])

    @mock.patch.object(discovery.InstanceDiscovery, "get_server")
    @mock.patch.object(discovery.InstanceDiscovery, "get_flavor_id")
    @mock.patch("ceilometer.compute.virt.libvirt.utils."
                "refresh_libvirt_connection")
    def test_discovery_with_libvirt_no_flavor_extra_specs(
            self, mock_libvirt_conn,
            mock_get_flavor_id, mock_get_server):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        self.CONF.set_override("fetch_extra_metadata", False, group="compute")
        mock_libvirt_conn.return_value = FakeConn(
            domains=[FakeDomain(
                metadata=LIBVIRT_METADATA_XML_NO_FLAVOR_EXTRA_SPECS)])
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())

        mock_get_flavor_id.assert_not_called()
        mock_get_server.assert_not_called()

        self.assertEqual(1, len(resources))
        r = list(resources)[0]
        s = util.make_sample_from_instance(self.CONF, r, "metric", "delta",
                                           "carrot", 1)

        metadata = s.resource_metadata
        self.assertEqual("m1.tiny", metadata["instance_type"])
        self.assertEqual({"name": "m1.tiny",
                          "id": "eba4213d-3c6c-4b5f-8158-dd0022d71d62",
                          "ram": 512,
                          "disk": 1,
                          "swap": 0,
                          "ephemeral": 0,
                          "vcpus": 1},
                         metadata["flavor"])

    @mock.patch("ceilometer.compute.virt.libvirt.utils."
                "refresh_libvirt_connection")
    def test_discovery_with_libvirt_from_volume_image(
            self, mock_libvirt_conn):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        self.CONF.set_override("fetch_extra_metadata", False, group="compute")
        mock_libvirt_conn.return_value = FakeConn(
            domains=[
                FakeDomain(metadata=LIBVIRT_METADATA_XML_FROM_VOLUME_IMAGE)])
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
        self.assertIsNone(metadata["image"])
        self.assertIn("image_meta", metadata)
        self.assertEqual({"base_image_ref",
                          "container_format",
                          "disk_format",
                          "min_disk",
                          "min_ram",
                          "os_distro",
                          "os_type"},
                         set(metadata["image_meta"].keys()))
        self.assertEqual("",
                         metadata["image_meta"]["base_image_ref"])
        self.assertEqual("bare",
                         metadata["image_meta"]["container_format"])
        self.assertEqual("raw",
                         metadata["image_meta"]["disk_format"])
        self.assertEqual("1",
                         metadata["image_meta"]["min_disk"])
        self.assertEqual("0",
                         metadata["image_meta"]["min_ram"])
        self.assertEqual("ubuntu",
                         metadata["image_meta"]["os_distro"])
        self.assertEqual("linux",
                         metadata["image_meta"]["os_type"])

    @mock.patch("ceilometer.compute.virt.libvirt.utils."
                "refresh_libvirt_connection")
    def test_discovery_with_libvirt_from_volume_no_image(
            self, mock_libvirt_conn):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        self.CONF.set_override("fetch_extra_metadata", False, group="compute")
        mock_libvirt_conn.return_value = FakeConn(
            domains=[
                FakeDomain(
                    metadata=LIBVIRT_METADATA_XML_FROM_VOLUME_NO_IMAGE)])
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())

        self.assertEqual(1, len(resources))
        r = list(resources)[0]
        s = util.make_sample_from_instance(self.CONF, r, "metric", "delta",
                                           "carrot", 1)

        metadata = s.resource_metadata
        self.assertIsNone(metadata["image"])
        self.assertIn("image_meta", metadata)
        self.assertEqual({"base_image_ref"},
                         set(metadata["image_meta"].keys()))
        self.assertEqual("",
                         metadata["image_meta"]["base_image_ref"])

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
            2016, 1, 1, minute=20, tzinfo=datetime.timezone.utc)
        resources = dsc.discover(mock.MagicMock())
        self.assertEqual(1, len(resources))

        self.utc_now.return_value = datetime.datetime(
            2016, 1, 1, minute=31, tzinfo=datetime.timezone.utc)
        resources = dsc.discover(mock.MagicMock())
        self.assertEqual(1, len(resources))

        expected_calls = [mock.call('test', None),
                          mock.call('test', '2016-01-01T00:00:00+00:00'),
                          mock.call('test', None)]
        self.assertEqual(expected_calls,
                         self.client.instance_get_all_by_host.call_args_list)

    @mock.patch("ceilometer.compute.virt.libvirt.utils."
                "refresh_libvirt_connection")
    def test_discovery_with_libvirt_error(self, mock_libvirt_conn):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        mock_libvirt_conn.return_value = FakeManualInstanceConn()
        dsc = discovery.InstanceDiscovery(self.CONF)
        resources = dsc.discover(mock.MagicMock())
        self.assertEqual(0, len(resources))

    def test_get_flavor_id(self):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        fake_flavor = argparse.Namespace(
            id="eba4213d-3c6c-4b5f-8158-dd0022d71d62")
        self.client.nova_client.flavors.find.return_value = fake_flavor
        dsc = discovery.InstanceDiscovery(self.CONF)
        self.assertEqual(fake_flavor.id, dsc.get_flavor_id("m1.tiny"))

    def test_get_flavor_id_notfound(self):
        self.CONF.set_override("instance_discovery_method",
                               "libvirt_metadata",
                               group="compute")
        self.client.nova_client.flavors.find.side_effect = (
            exceptions.NotFound(404))
        dsc = discovery.InstanceDiscovery(self.CONF)
        self.assertIsNone(dsc.get_flavor_id("m1.tiny"))

    def test_get_server(self):
        self.client.nova_client = mock.MagicMock()
        self.client.nova_client.servers = mock.MagicMock()

        fake_server = mock.MagicMock()
        fake_server.metadata = {'metering.server_group': 'group1'}

        fake_flavor = mock.MagicMock()
        fake_flavor.id = 'fake_id'
        fake_server.flavor = fake_flavor

        self.client.nova_client.servers.get = mock.MagicMock(
            return_value=fake_server)
        dsc = discovery.InstanceDiscovery(self.CONF)

        uuid = '123456'

        ret_server = dsc.get_server(uuid)
        self.assertEqual('fake_id', ret_server.flavor.id)
        self.assertEqual({'metering.server_group': 'group1'},
                         ret_server.metadata)

        # test raise NotFound exception
        self.client.nova_client.servers.get = mock.MagicMock(
            side_effect=exceptions.NotFound(404))
        dsc = discovery.InstanceDiscovery(self.CONF)

        ret_server = dsc.get_server(uuid)
        self.assertIsNone(ret_server)
