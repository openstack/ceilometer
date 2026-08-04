# Copyright (C) 2026 Red Hat
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


import openstack
from openstack.block_storage.v3 import backup as cinder_backup
from openstack.block_storage.v3 import service as cinder_service
from openstack.block_storage.v3 import snapshot as cinder_snapshot
from openstack.block_storage.v3 import stats as cinder_stats
from openstack.block_storage.v3 import volume as cinder_volume
from openstack.dns.v2 import recordset
from openstack.dns.v2 import zone
from openstack.identity.v3 import domain as sdk_domain
from openstack.identity.v3 import project as sdk_project
from openstack.load_balancer.v2 import load_balancer as sdk_load_balancer
from openstack.network.v2 import firewall_group as sdk_firewall_group
from openstack.network.v2 import firewall_policy as sdk_firewall_policy
from openstack.network.v2 import floating_ip as sdk_floating_ip
from openstack.network.v2 import vpn_ipsec_site_connection as sdk_ipsec_conn
from openstack.network.v2 import vpn_service as sdk_vpn_service
from openstack.shared_file_system.v2 import share as sdk_share

from ceilometer import keystone_client


DOMAIN_DEFAULT_ceilo = keystone_client.Domain(
    id='default', name='Default', is_enabled=True)
DOMAIN_DEFAULT_sdk = sdk_domain.Domain(
    connection=None,
    id='default', name='Default',
    is_enabled=True)

DOMAIN_HEAT_ceilo = keystone_client.Domain(
    id='2f42ab40b7ad4140815ef830d816a16c', name='heat', is_enabled=True)
DOMAIN_HEAT_sdk = sdk_domain.Domain(
    connection=None,
    id='2f42ab40b7ad4140815ef830d816a16c', name='heat',
    is_enabled=True)

DOMAIN_DISABLED_ceilo = keystone_client.Domain(
    id='disabled-domain', name='Disabled', is_enabled=False)
DOMAIN_DISABLED_sdk = sdk_domain.Domain(
    connection=None,
    id='disabled-domain', name='Disabled',
    is_enabled=False)

PROJECT_ADMIN_ceilo = keystone_client.Project(
    id='2ce92449a23145ef9c539f3327960ce3', name='admin', parent_id='default',
    domain_id='default', is_domain=False, is_enabled=True)
PROJECT_ADMIN_sdk = sdk_project.Project(
    connection=None,
    id='2ce92449a23145ef9c539f3327960ce3', name='admin',
    parent_id='default', domain_id='default',
    is_domain=False, is_enabled=True)

PROJECT_SERVICE_ceilo = keystone_client.Project(
    id='a2d42c23-d518-46b6-96ab-3fba2e146859', name='service',
    parent_id='default', domain_id='default', is_domain=False, is_enabled=True)
PROJECT_SERVICE_sdk = sdk_project.Project(
    connection=None,
    id='a2d42c23-d518-46b6-96ab-3fba2e146859', name='service',
    domain_id='default', parent_id='default',
    is_domain=False, is_enabled=True)

PROJECT_DEMO_ceilo = keystone_client.Project(
    id='57d96b9af18d43bb9d047f436279b0be', name='demo',
    parent_id='default', domain_id='2f42ab40b7ad4140815ef830d816a16c',
    is_domain=False, is_enabled=True)
PROJECT_DEMO_sdk = sdk_project.Project(
    connection=None,
    id='57d96b9af18d43bb9d047f436279b0be', name='demo',
    domain_id='2f42ab40b7ad4140815ef830d816a16c', parent_id='default',
    is_domain=False, is_enabled=True)

PROJECT_DISABLED_ceilo = keystone_client.Project(
    id='disabled-project', name='disabled', parent_id='default',
    domain_id='default', is_domain=False, is_enabled=False)
PROJECT_DISABLED_sdk = sdk_project.Project(
    connection=None,
    id='disabled-project', name='disabled',
    parent_id='default', domain_id='default',
    is_domain=False, is_enabled=False)


# These are the default set of keystone resources that are used to populate
# FakeKeyStoneClient and FakeConnection if no project or domain parameters
# are passed to the constructor
DEFAULT_PROJECTS_ceilo = [
    PROJECT_ADMIN_ceilo, PROJECT_SERVICE_ceilo,
    PROJECT_DEMO_ceilo, PROJECT_DISABLED_ceilo]
DEFAULT_PROJECTS_sdk = [
    PROJECT_ADMIN_sdk, PROJECT_SERVICE_sdk,
    PROJECT_DEMO_sdk, PROJECT_DISABLED_sdk]

DEFAULT_DOMAINS_ceilo = [DOMAIN_HEAT_ceilo, DOMAIN_DEFAULT_ceilo]
DEFAULT_DOMAINS_sdk = [DOMAIN_HEAT_sdk, DOMAIN_DEFAULT_sdk]


#####################
# SDK Fakes
#####################

RECORDSET_1 = recordset.Recordset(
    connection=None,
    id='rs-1-uuid',
    name='www.example.com.',
    type='A',
    records=['192.168.1.1'],
    ttl=3600,
)

RECORDSET_2 = recordset.Recordset(
    connection=None,
    id='rs-2-uuid',
    name='mail.example.com.',
    type='MX',
    records=['10 mail.example.com.'],
    ttl=3600,
)

ZONE_1 = zone.Zone(
    connection=None,
    id='zone-1-uuid',
    name='example.com.',
    email='admin@example.com',
    ttl=3600,
    description='Example zone',
    type='PRIMARY',
    status='ACTIVE',
    action='NONE',
    serial=1234567890,
    pool_id='pool-1',
    project_id='tenant-1-uuid',
)

ZONE_2 = zone.Zone(
    connection=None,
    id='zone-2-uuid',
    name='test.org.',
    email='admin@test.org',
    ttl=7200,
    description='Test zone',
    type='PRIMARY',
    status='PENDING',
    action='CREATE',
    serial=1234567891,
    pool_id='pool-1',
    project_id='tenant-2-uuid',
)

ZONE_3 = zone.Zone(
    connection=None,
    id='zone-3-uuid',
    name='error.net.',
    email='admin@error.net',
    ttl=1800,
    description='Error zone',
    type='PRIMARY',
    status='ERROR',
    action='UPDATE',
    serial=1234567892,
    pool_id='pool-2',
    project_id='tenant-1-uuid',
)

ZONE_UNKNOWN_STATUS = zone.Zone(
    connection=None,
    id='zone-unknown-uuid',
    name='unknown.com.',
    email='admin@unknown.com',
    ttl=3600,
    description='Unknown zone',
    type='PRIMARY',
    status='UNKNOWN_STATUS',
    action='NONE',
    serial=1234567893,
    pool_id='pool-1',
    project_id='tenant-1-uuid',
)


LB_1 = sdk_load_balancer.LoadBalancer(
    connection=None,
    id='lb-1-uuid',
    name='my-lb-1',
    availability_zone='az-1',
    vip_address='192.168.1.10',
    vip_port_id='port-1-uuid',
    provisioning_status='ACTIVE',
    operating_status='ONLINE',
    provider='amphora',
    flavor_id='flavor-1',
    project_id='tenant-1-uuid',
)

LB_2 = sdk_load_balancer.LoadBalancer(
    connection=None,
    id='lb-2-uuid',
    name='my-lb-2',
    availability_zone='az-2',
    vip_address='192.168.1.11',
    vip_port_id='port-2-uuid',
    provisioning_status='PENDING_UPDATE',
    operating_status='OFFLINE',
    provider='amphora',
    flavor_id='flavor-1',
    project_id='tenant-2-uuid',
)

LB_3 = sdk_load_balancer.LoadBalancer(
    connection=None,
    id='lb-3-uuid',
    name='my-lb-3',
    availability_zone=None,
    vip_address='192.168.1.12',
    vip_port_id='port-3-uuid',
    provisioning_status='ERROR',
    operating_status='ERROR',
    provider='amphora',
    flavor_id='flavor-1',
    project_id='tenant-1-uuid',
)

LB_4 = sdk_load_balancer.LoadBalancer(
    connection=None,
    id='lb-4-uuid',
    name='my-lb-4',
    availability_zone='az-1',
    vip_address='192.168.1.13',
    vip_port_id='port-4-uuid',
    provisioning_status='PENDING_DELETE',
    operating_status='DEGRADED',
    provider='amphora',
    flavor_id='flavor-1',
    project_id='tenant-1-uuid',
)

LB_UNKNOWN_OPERATING_STATUS = sdk_load_balancer.LoadBalancer(
    connection=None,
    id='lb-unknown-uuid',
    name='my-lb-unknown',
    availability_zone=None,
    vip_address='192.168.1.99',
    vip_port_id='port-unknown-uuid',
    provisioning_status='ACTIVE',
    operating_status='UNKNOWN_STATUS',
    provider='amphora',
    flavor_id='flavor-1',
    project_id='tenant-1-uuid',
)

LB_UNKNOWN_PROVISIONING_STATUS = sdk_load_balancer.LoadBalancer(
    connection=None,
    id='lb-unknown-uuid',
    name='my-lb-unknown',
    availability_zone=None,
    vip_address='192.168.1.99',
    vip_port_id='port-unknown-uuid',
    provisioning_status='UNKNOWN_STATUS',
    operating_status='ONLINE',
    provider='amphora',
    flavor_id='flavor-1',
    project_id='tenant-1-uuid',
)


class FakeSDKOctaviaClient:

    default_load_balancers = [LB_1, LB_2, LB_3, LB_4]

    def __init__(self, load_balancers=None):
        self._load_balancers = (load_balancers if load_balancers is not None
                                else self.default_load_balancers)

    def load_balancers(self):
        return iter(self._load_balancers)


SHARE_1 = sdk_share.Share(
    connection=None,
    id='share-1-uuid',
    name='my-share-1',
    availability_zone='az-1',
    share_protocol='NFS',
    share_type='default',
    share_network_id='network-1-uuid',
    status='available',
    host='host-1',
    is_public=False,
    size=100,
    project_id='tenant-1-uuid',
)

SHARE_2 = sdk_share.Share(
    connection=None,
    id='share-2-uuid',
    name='my-share-2',
    availability_zone='az-2',
    share_protocol='CIFS',
    share_type='default',
    share_network_id='network-2-uuid',
    status='creating',
    host='host-2',
    is_public=True,
    size=50,
    project_id='tenant-2-uuid',
)

SHARE_3 = sdk_share.Share(
    connection=None,
    id='share-3-uuid',
    name='my-share-3',
    availability_zone=None,
    share_protocol='NFS',
    share_type='default',
    share_network_id='network-3-uuid',
    status='error',
    host='host-3',
    is_public=False,
    size=200,
    project_id='tenant-1-uuid',
)

SHARE_UNKNOWN_STATUS = sdk_share.Share(
    connection=None,
    id='share-unknown-uuid',
    name='my-share-unknown',
    availability_zone=None,
    share_protocol='NFS',
    share_type='default',
    share_network_id='network-unknown-uuid',
    status='UNKNOWN_STATUS',
    host='host-unknown',
    is_public=False,
    size=100,
    project_id='tenant-1-uuid',
)


class FakeSDKManilaClient:

    default_shares = [SHARE_1, SHARE_2, SHARE_3]

    def __init__(self, shares=None):
        self._shares = shares if shares is not None else self.default_shares

    def shares(self, all_projects=True):
        return iter(self._shares)


class FakeSDKDesignateClient:

    default_recordsets = [RECORDSET_1, RECORDSET_2]
    default_zones = [ZONE_1, ZONE_2, ZONE_3]

    def __init__(self, zones=None, recordsets=None):
        self._zones = zones if zones is not None else self.default_zones
        self._recordsets = (recordsets if recordsets is not None
                            else self.default_recordsets)

    def zones(self, all_projects=True):
        return iter(self._zones)

    def recordsets(self, zone, all_projects=True):
        return iter(self._recordsets)


class FakeSession:
    """Minimal fake for keystoneauth1.session.Session.

    Exposes only the attributes accessed by ceilometer's keystone_client
    helper functions: get_service_catalog(), get_auth_token(), url_for(),
    and get_urls() all call session.auth.get_access(session).
    """

    class FakeAuth:
        def get_access(self, session):
            return "fake_token"

    def __init__(self):
        self.auth = self.FakeAuth()


class FakeSDKCinderClient:

    def __init__(
            self, volumes=None, snapshots=None, backups=None,
            pools=None, services=None):
        self._volumes = volumes if volumes is not None else VOLUME_LIST
        self._snapshots = snapshots if snapshots is not None else SNAPSHOT_LIST
        self._backups = backups if backups is not None else BACKUP_LIST
        self._pools = pools if pools is not None else POOL_LIST
        self._services = services if services is not None else SERVICE_LIST

    def volumes(self, *, details=True, all_projects=False, **query):
        return iter(self._volumes)

    def snapshots(self, *, details=True, **query):
        return iter(self._snapshots)

    def backups(self, *, details=True, **query):
        return iter(self._backups)

    def backend_pools(self, **query):
        return iter(self._pools)

    def services(self, **query):
        return iter(self._services)


class FakeSDKNetworkClient:

    def ips(self):
        FLOATING_IP_0 = sdk_floating_ip.FloatingIP(
            connection=None,
            id='fip-123',
            floating_ip_address='192.168.1.100',
            fixed_ip_address='10.0.0.5',
            status='ACTIVE',
            project_id='project-abc',
            router_id='router-456'
        )
        return iter([FLOATING_IP_0])

    def firewall_groups(self):
        FIREWALL_GROUP_0 = sdk_firewall_group.FirewallGroup(
            connection=None,
            id='fw-123',
            name='my-firewall',
            status='ACTIVE',
            project_id='project-abc',
            ingress_firewall_policy_id='policy-1',
            egress_firewall_policy_id='policy-2'
        )
        return iter([FIREWALL_GROUP_0])

    def firewall_policies(self):
        FIREWALL_POLICY_0 = sdk_firewall_policy.FirewallPolicy(
            connection=None,
            id='policy-123',
            name='my-policy',
            project_id='project-abc',
            firewall_rules=['rule-1', 'rule-2']
        )
        return iter([FIREWALL_POLICY_0])

    def vpn_ipsec_site_connections(self):
        VPN_IPSEC_CONN_0 = sdk_ipsec_conn.VpnIPSecSiteConnection(
            connection=None,
            id='ipsec-123',
            name='my-ipsec',
            status='ACTIVE',
            project_id='project-abc'
        )

        return iter([VPN_IPSEC_CONN_0])

    def vpn_services(self):

        VPN_SERVICE_0 = sdk_vpn_service.VpnService(
            connection=None,
            id='vpn-123',
            name='my-vpn',
            status='ACTIVE',
            project_id='project-abc'
        )

        return iter([VPN_SERVICE_0])


IMAGE_UBUNTU = openstack.image.v2.image.Image(
    connection=None,
    status="active", visibility="public",
    name="ubuntu-12.04-x86",
    container_format="bare",
    created_at="2026-07-23T16:31:34Z",
    disk_format="raw",
    updated_at="2026-08-06T16:31:34Z",
    min_disk=1,
    protected=False,
    checksum="4708c575c7bc57bea8d112c64a5a6fa1",
    min_ram=0,
    tags=[],
    virtual_size=2000000000,
    size=250000000,
    owner="2d1689c3a5d3482a98544acaa7edef2f",
    id="a1f4684e-58bd-4c88-aefd-2ecb0783b497",
)

IMAGE_1 = openstack.image.v2.image.Image(
    connection=None,
    id=1, name='ubuntu-12.04-x86',
    kernel_id=11, ramdisk_id=21,
    disk_format='qcow2', container_format='bare',
    min_disk=1, min_ram=0, os_distro='ubuntu', os_type='linux')

IMAGE_2 = openstack.image.v2.image.Image(
    connection=None,
    id=2, name='rhel-6-x64',
    kernel_id=12, ramdisk_id=22,
    disk_format='qcow2', container_format='bare',
    min_disk=0, min_ram=0)

IMAGE_MISSING_METADATA = openstack.image.v2.image.Image(
    connection=None,
    id=3, name='rhel-6-x64',
    kernel_id=None, ramdisk_id=None,
    disk_format='qcow2', container_format='bare',
    min_disk=0, min_ram=0)

IMAGE_MISSING_KERNEL_RAMDISK = openstack.image.v2.image.Image(
    connection=None,
    id=4, name='rhel-6-x64',
    kernel_id=None, ramdisk_id=None,
    disk_format='qcow2', container_format='bare',
    min_disk=0, min_ram=0)

IMAGE_MISSING_RAMDISK = openstack.image.v2.image.Image(
    connection=None,
    id=5, name='rhel-6-x64-missing-ramdisk',
    kernel_id=11, ramdisk_id=None,
    disk_format='qcow2', container_format='bare',
    min_disk=0, min_ram=0)

IMAGE_MISSING_KERNEL = openstack.image.v2.image.Image(
    connection=None,
    id=6, name='rhel-6-x64-missing-kernel',
    kernel_id=None, ramdisk_id=21,
    disk_format='qcow2', container_format='bare',
    min_disk=0, min_ram=0)

IMAGE_FEDORA = openstack.image.v2.image.Image(
    connection=None,
    name="Fedora-Cloud-Base-37-1.7.x86_64",
    disk_format="qcow2", container_format="bare",
    visibility="public", size=492830720, virtual_size=5368709120,
    status="active", checksum="36f7b464b6ab46ad97c001b539495e90",
    protected=False, min_ram=0, min_disk=0,
    owner="2d1689c3a5d3482a98544acaa7edef2f",
    id="32ab7d96-fabf-4d1a-a8af-38d0fe3a2b92", tags=[],
)
IMAGE_AMPHORA = openstack.image.v2.image.Image(
    connection=None,
    name="amphora-x64-haproxy",
    disk_format="qcow2", container_format="bare",
    visibility="public", size=379393024, virtual_size=2147483648,
    status="active", checksum="9a78cb8545b522bd59a3a31d5a131468",
    protected=False, min_ram=0, min_disk=0,
    owner="2d1689c3a5d3482a98544acaa7edef2f",
    id="1cfa6322-5302-4b2d-9748-3b230ea4447d",
    created_at="2026-01-26T14:36:30Z",
    updated_at="2026-01-26T14:36:39Z", tags=['amphora'],
)
IMAGE_CIRROS = openstack.image.v2.image.Image(
    connection=None,
    name="cirros-0.6.3-x86_64-disk",
    disk_format="qcow2", container_format="bare",
    visibility="public", size=21692416, virtual_size=117440512,
    status="active", checksum="87617e24a5e30cb3b87fda8c0764838f",
    protected=False, min_ram=0, min_disk=0,
    owner="2d1689c3a5d3482a98544acaa7edef2f",
    id="8e16de93-6ba5-42a7-8fbd-679607110d7a",
    created_at="2026-01-26T14:35:30Z",
    updated_at="2026-01-26T14:35:31Z",
    tags=[],
)
IMAGE_CIRROS_DISK = openstack.image.v2.image.Image(
    connection=None,
    name="cirros-0.6.1-x86_64-disk",
    disk_format="qcow2", container_format="bare",
    visibility="public", size=21233664, virtual_size=117440512,
    status="active", protected=False, min_ram=0, min_disk=0,
    owner="2d1689c3a5d3482a98544acaa7edef2f",
    id="389c678d-4686-4426-ba7c-0697f065c520",
    created_at="2026-01-26T14:35:27Z",
    updated_at="2026-01-26T14:35:29Z", tags=[],
)

IMAGE_LIST = [
    IMAGE_FEDORA, IMAGE_AMPHORA,
    IMAGE_CIRROS, IMAGE_CIRROS_DISK,
    IMAGE_UBUNTU, IMAGE_1, IMAGE_2]


class FakeSDKImageClient:
    """Fake openstack/image/v2/_proxy.Proxy."""
    def __init__(self, images=None):
        self._images = images if images is not None else IMAGE_LIST

    def images(self, **query):
        """Return a generator of images

        :param kwargs query: Optional query parameters to be sent to limit
            the resources being returned.

        :returns: A generator of image objects
        :rtype: :class:`~openstack.image.v2.image.Image`
        """
        if query:
            raise NotImplementedError(
                "FakeSDKImageClient.images does not support query param")
        return iter(self._images)

    def get_image(self, image):
        """Get a single image

        :param image: The value can be the ID of a image or a
            :class:`~openstack.image.v2.image.Image` instance.

        :returns: One :class:`~openstack.image.v2.image.Image`
        :raises: :class:`~openstack.exceptions.NotFoundException`
            when no resource can be found.
        """
        if isinstance(image, openstack.image.v2.image.Image):
            image_id = image.id
        else:
            image_id = image

        image_list = [i for i in self.images() if i.id == image_id]
        try:
            return image_list[0]
        except IndexError:
            raise openstack.exceptions.NotFoundException


class FakeConnection:
    """Fake connection object for testing."""

    def __init__(self, session=None, domains=None, projects=None, zones=None,
                 recordsets=None, shares=None, load_balancers=None,
                 volumes=None, snapshots=None, backups=None, pools=None,
                 services=None, images=None):
        """Initialize FakeConnection.

        :param projects: Optional list of SDK Project objects. Defaults to the
            class-level SDK_PROJECT_* fixtures.
        :param domains: Optional list of SDK Domain objects. Defaults to the
            class-level DOMAIN_* fixtures.
        :param zones: Optional list of SDK Zone objects. Passed to
            FakeSDKDesignateClient.
        :param recordsets: Optional list of SDK RecordSet objects. Passed to
            FakeSDKDesignateClient.
        :param shares: Optional list of SDK Share objects. Passed to
            FakeSDKManilaClient.
        :param load_balancers: Optional list of SDK LoadBalancer objects.
            Passed to FakeSDKOctaviaClient.
        :param volumes: Optional list of SDK Volumes. Passed to
            FakeSDKCinderClient.
        :param snapshots: Optional list of SDK Volume Snapshots. Passed to
            FakeSDKCinderClient.
        :param backups: Optional list of SDK Volume Backups. Passed to
            FakeSDKCinderClient.
        :param pools: Optional list of SDK Volume Pools. Passed to
            FakeSDKCinderClient.
        :param services: Optional list of SDK Volume Service. Passed to
            FakeSDKCinderClient.
        :param images: Optional list of SDK Image objects. Passed to
            FakeSDKImageClient.
        """

        self.dns = FakeSDKDesignateClient(zones=zones, recordsets=recordsets)
        self.shared_file_system = FakeSDKManilaClient(shares=shares)
        self.load_balancer = FakeSDKOctaviaClient(
            load_balancers=load_balancers)
        self.network = FakeSDKNetworkClient()
        self.image = FakeSDKImageClient(images=images)
        self.session = session or FakeSession()
        # Don't use a short-circuit or here. The explicit check for None is
        # needed since [] is falsey, but is a valid input e.g. to create a
        # connection with no projects
        self._domains = domains if domains is not None else DEFAULT_DOMAINS_sdk
        self._projects = (
            projects if projects is not None else DEFAULT_PROJECTS_sdk)

        self.block_storage = FakeSDKCinderClient(
            volumes=volumes,
            snapshots=snapshots,
            backups=backups,
            pools=pools,
            services=services)

    def list_projects(self, domain_id=None, name_or_id=None, filters=None):
        """List projects.

        emulates openstacksdk/cloud/_identity.py:list_projects

        With no parameters, returns a full listing of all visible projects.

        :param domain_id: Domain ID to scope the searched projects.
        :param name_or_id: Name or ID of the project(s).
        :param filters: A dictionary of meta data to use for further filtering.

        :returns: A list of identity ``Project`` objects.
        :raises: :class:`~openstack.exceptions.SDKException` if something goes
            wrong during the OpenStack API call.
        """
        result = list(self._projects)

        # Filter by domain_id
        if domain_id:
            result = [p for p in result if p.domain_id == domain_id]

        # Filter by name_or_id
        if name_or_id:
            result = [p for p in result
                      if p.name == name_or_id or p.id == name_or_id]

        # Apply additional filters
        # SDK resources expose boolean fields as is_<field> (e.g. is_enabled),
        # so fall back to the is_ variant if the raw key is not found.
        if filters:
            for key, value in filters.items():
                result = [p for p in result
                          if getattr(p, key,
                                     getattr(p, 'is_' + key, None)) == value]

        return result

    def search_projects(self, name_or_id=None, filters=None, domain_id=None):
        """Search projects.

        emulates openstacksdk/cloud/_identity.py:search_projects

        :param name_or_id: Name or ID of the project(s).
        :param filters: A dictionary of meta data to use for further filtering.
        :param domain_id: Domain ID to scope the searched projects.

        :returns: A list of identity ``Project`` objects.
        :raises: :class:`~openstack.exceptions.SDKException` if something goes
            wrong during the OpenStack API call.
        """
        result = self.list_projects(domain_id=domain_id, filters=filters)

        if name_or_id:
            result = [p for p in result
                      if p.name == name_or_id or p.id == name_or_id]

        return result

    def search_domains(self, name_or_id=None, filters=None):
        """Search domains.

        emulates openstacksdk/cloud/_identity.py:search_domains

        :param name_or_id: Name or ID of the domain(s).
        :param filters: A dictionary of meta data to use for further filtering.

        :returns: A list of identity ``Domain`` objects.
        :raises: :class:`~openstack.exceptions.SDKException` if something goes
            wrong during the OpenStack API call.
        """
        result = list(self._domains)

        if name_or_id:
            result = [d for d in result
                      if d.name == name_or_id or d.id == name_or_id]

        if filters:
            for key, value in filters.items():
                result = [d for d in result
                          if getattr(d, key,
                                     getattr(d, 'is_' + key, None)) == value]

        return result

    def list_domains(self, filters=None):
        """List Keystone domains.

        emulates openstacksdk/cloud/_identity.py:list_domains

        :param filters: A dictionary of meta data to use for further filtering.

        :returns: A list of identity ``Domain`` objects.
        :raises: :class:`~openstack.exceptions.SDKException` if something goes
            wrong during the OpenStack API call.
        """
        return self.search_domains(filters=filters)


#####################
# Cinder Fakes
#####################

VOLUME = cinder_volume.Volume(connection=None, **{
    'migration_status': None,
    'attachments': [
        {'server_id': '1ae69721-d071-4156-a2bd-b11bb43ec2e3',
         'attachment_id': 'f903d95e-f999-4a34-8be7-119eadd9bb4f',
         'attached_at': '2016-07-14T03:55:57.000000',
         'host_name': None,
         'volume_id': 'd94c18fb-b680-4912-9741-da69ee83c94f',
         'device': '/dev/vdb',
         'id': 'd94c18fb-b680-4912-9741-da69ee83c94f'}],
    'links': [
        {'href': 'http://fake_link3', 'rel': 'self'},
        {'href': 'http://fake_link4', 'rel': 'bookmark'}],
    'availability_zone': 'nova',
    'os-vol-host-attr:host': 'test@lvmdriver-1#lvmdriver-1',
    'encrypted': False,
    'updated_at': '2016-07-14T03:55:57.000000',
    'replication_status': 'disabled',
    'snapshot_id': None,
    'id': 'd94c18fb-b680-4912-9741-da69ee83c94f',
    'size': 1,
    'user_id': 'be255bd31eb944578000fc762fde6dcf',
    'os-vol-tenant-attr:tenant_id': '6824974c08974d4db864bbaa6bc08303',
    'os-vol-mig-status-attr:migstat': None,
    'metadata': {'readonly': 'False', 'attached_mode': 'rw'},
    'status': 'in-use',
    'description': None,
    'multiattach': False,
    'source_volid': None,
    'consistencygroup_id': None,
    'volume_image_metadata': {
        'checksum': '17d9daa4fb8e20b0f6b7dec0d46fdddf',
        'container_format': 'bare',
        'disk_format': 'raw',
        'hw_disk_bus': 'scsi',
        'hw_scsi_model': 'virtio-scsi',
        'image_id': 'f0019ee3-523c-45ab-b0b6-3adc529673e7',
        'image_name': 'debian-jessie-scsi',
        'min_disk': '0',
        'min_ram': '0',
        'size': '1572864000',
    },
    'os-vol-mig-status-attr:name_id': None,
    'group_id': None,
    'provider_id': None,
    'shared_targets': False,
    'service_uuid': '2f6b5a18-0cd5-4421-b97e-d2c3e85ed758',
    'cluster_name': None,
    'volume_type_id': '65a9f65a-4696-4435-a09d-bc44d797c529',
    'name': None,
    'bootable': 'false',
    'created_at': '2016-06-23T08:27:45.000000',
    'volume_type': 'lvmdriver-1',
})
SNAPSHOT = cinder_snapshot.Snapshot(connection=None, **{
    'status': 'available',
    'os-extended-snapshot-attributes:progress': '100%',
    'description': None,
    'os-extended-snapshot-attributes:project_id':
        '6824974c08974d4db864bbaa6bc08303',
    'size': 1,
    'user_id': 'be255bd31eb944578000fc762fde6dcf',
    'updated_at': '2016-10-19T07:56:55.000000',
    'id': 'b1ea6783-f952-491e-a4ed-23a6a562e1cf',
    'volume_id': '6f27bc42-c834-49ea-ae75-8d1073b37806',
    'metadata': {},
    'created_at': '2016-10-19T07:56:55.000000',
    'group_snapshot_id': None,
    'name': None,
})
BACKUP = cinder_backup.Backup(connection=None, **{
    'status': 'available',
    'object_count': 0,
    'container': None,
    'name': None,
    'links': [
        {'href': 'http://fake_urla', 'rel': 'self'},
        {'href': 'http://fake_urlb', 'rel': 'bookmark'}],
    'availability_zone': 'nova',
    'created_at': '2016-10-19T06:55:23.000000',
    'snapshot_id': None,
    'updated_at': '2016-10-19T06:55:23.000000',
    'data_timestamp': '2016-10-19T06:55:23.000000',
    'description': None,
    'has_dependent_backups': False,
    'volume_id': '6f27bc42-c834-49ea-ae75-8d1073b37806',
    'os-backup-project-attr:project_id': '6824974c08974d4db864bbaa6bc08303',
    'fail_reason': '',
    'is_incremental': False,
    'metadata': {},
    'user_id': 'be255bd31eb944578000fc762fde6dcf',
    'id': '75a52125-85ff-4a8d-b2aa-580f3b22273f',
    'size': 1,
})
POOL_LVM = cinder_stats.Pools(connection=None, **{
    'name': 'localhost.localdomain@lvmdriver-1#lvmdriver-1',
    'capabilities': {
        'pool_name': 'lvmdriver-1',
        'total_capacity_gb': 28.5,
        'free_capacity_gb': 28.39,
        'reserved_percentage': 0,
        'location_info':
            'LVMVolumeDriver:localhost.localdomain:stack-volumes:thin:0',
        'QoS_support': False,
        'provisioned_capacity_gb': 4.0,
        'max_over_subscription_ratio': 20.0,
        'thin_provisioning_support': True,
        'thick_provisioning_support': False,
        'total_volumes': 3,
        'filter_function': None,
        'goodness_function': None,
        'multiattach': True,
        'backend_state': 'up',
        'allocated_capacity_gb': 4,
        'cacheable': True,
        'volume_backend_name': 'lvmdriver-1',
        'storage_protocol': 'iSCSI',
        'vendor_name': 'Open Source',
        'driver_version': '3.0.0',
        'timestamp': '2025-03-21T14:19:02.901750',
    },
})

POOL_CEPH = cinder_stats.Pools(connection=None, **{
    'name': 'cinder-3ceee-volume-ceph-0@ceph#ceph',
    'capabilities': {
        'vendor_name': 'Open Source',
        'driver_version': '1.3.0',
        'storage_protocol': 'ceph',
        'total_capacity_gb': 85.0,
        'free_capacity_gb': 85.0,
        'reserved_percentage': 0,
        'multiattach': True,
        'thin_provisioning_support': True,
        'max_over_subscription_ratio': '20.0',
        'location_info':
            'ceph:/etc/ceph/ceph.conf:a94b63c4e:openstack:volumes',
        'backend_state': 'up',
        'QoS_support': True,
        'volume_backend_name': 'ceph',
        'replication_enabled': False,
        'allocated_capacity_gb': 1,
        'filter_function': None,
        'goodness_function': None,
        'timestamp': '2025-06-09T13:29:43.286226',
    },
})

POOL_ZERO_ALLOCATED_CAPACITY = cinder_stats.Pools(connection=None, **{
    'name': 'localhost.localdomain@lvmdriver-1#lvmdriver-1',
    'capabilities': {
        'allocated_capacity_gb': 0,
    },
})
POOL_NO_CAPABILITIES = cinder_stats.Pools(connection=None, **{
    'name': 'localhost.localdomain@lvmdriver-1#lvmdriver-1',
})

# Test fixture for VirtualFree pollster when provisioned_capacity_gb is
# missing. The pollster uses getattr(pool, 'provisioned_capacity_gb', None)
# as a guard, so pools missing this attribute are silently skipped
# (yield no samples).
POOL_NO_PROVISIONED_CAPACITY = cinder_stats.Pools(connection=None, **{
    'name': 'localhost.localdomain@lvmdriver-2#lvmdriver-2',
    'capabilities': {
        'pool_name': 'lvmdriver-2',
        'total_capacity_gb': 28.5,
        'free_capacity_gb': 28.39,
        'reserved_percentage': 0,
        'max_over_subscription_ratio': 20.0,
        'thin_provisioning_support': True,
        'allocated_capacity_gb': 4,
    }
})

# Test fixture for VirtualFree pollster when thin_provisioning_support is
# missing. When provisioned_capacity_gb IS set but thin_provisioning_support
# is missing, the pollster attempts to access the attribute and raises
# AttributeError.
POOL_NO_THIN_PROVISIONING = cinder_stats.Pools(connection=None, **{
    'name': 'localhost.localdomain@lvmdriver-3#lvmdriver-3',
    'capabilities': {
        'pool_name': 'lvmdriver-3',
        'total_capacity_gb': 28.5,
        'free_capacity_gb': 28.39,
        'reserved_percentage': 0,
        'provisioned_capacity_gb': 4.0,
        'max_over_subscription_ratio': 20.0,
        'allocated_capacity_gb': 4,
    }
})

# Test fixture for VirtualFree pollster with thick provisioning.
# When thin_provisioning_support=False, max_over_subscription_ratio defaults to
# 1.0 in the calculation: 1.0 * (28.5 - 0) - 4.0 = 24.5 virtual free capacity.
POOL_THICK_PROVISIONING = cinder_stats.Pools(connection=None, **{
    'name': 'localhost.localdomain@lvmdriver-4#lvmdriver-4',
    'capabilities': {
        'pool_name': 'lvmdriver-4',
        'total_capacity_gb': 28.5,
        'free_capacity_gb': 28.39,
        'reserved_percentage': 0,
        'provisioned_capacity_gb': 4.0,
        'max_over_subscription_ratio': 20.0,
        'thin_provisioning_support': False,
        'allocated_capacity_gb': 4,
    }
})

# Test fixture for VirtualFree pollster when reserved_percentage is not set
POOL_NO_RESERVED_PERCENTAGE = cinder_stats.Pools(connection=None, **{
    'name': 'mypool',
    'capabilities': {
        'provisioned_capacity_gb': 100, }})

SERVICE_CINDER_VOLUME = cinder_service.Service(connection=None, **{
    'binary': 'cinder-volume',
    'host': 'devstack',
    'zone': 'nova',
    'status': 'enabled',
    'state': 'up'})
SERVICE_CINDER_SCHED = cinder_service.Service(connection=None, **{
    'binary': 'cinder-scheduler',
    'host': 'devstack',
    'zone': 'nova',
    'status': 'enabled',
    'state': 'up'})
SERVICE_CINDER_BACKUP = cinder_service.Service(connection=None, **{
    'binary': 'cinder-backup',
    'host': 'devstack',
    'zone': 'nova',
    'status': 'enabled',
    'state': 'down'})
SERVICE_CINDER_UNKNOWN_STATUS = cinder_service.Service(connection=None, **{
    'binary': 'cinder-volume',
    'host': 'devstack',
    'zone': 'nova',
    'status': 'enabled',
    'state': 'unknown'})

VOLUME_LIST = [VOLUME]
SNAPSHOT_LIST = [SNAPSHOT]
BACKUP_LIST = [BACKUP]
POOL_LIST = [POOL_LVM, POOL_CEPH]
SERVICE_LIST = [
    SERVICE_CINDER_VOLUME, SERVICE_CINDER_SCHED, SERVICE_CINDER_BACKUP]
