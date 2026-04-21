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


from cinderclient.v3 import pools as cinder_pools
from cinderclient.v3 import services as cinder_services
from cinderclient.v3 import volume_backups as cinder_backups
from cinderclient.v3 import volume_snapshots as cinder_snapshots
from cinderclient.v3 import volumes as cinder_volumes
from keystoneauth1 import exceptions as ka_exceptions
from keystoneclient import exceptions as ks_exceptions
from keystoneclient.v3 import domains as ks_domains
from keystoneclient.v3 import projects as ks_projects
from openstack.identity.v3 import domain as sdk_domain
from openstack.identity.v3 import project as sdk_project
from openstack.network.v2 import firewall_group as sdk_firewall_group
from openstack.network.v2 import firewall_policy as sdk_firewall_policy
from openstack.network.v2 import floating_ip as sdk_floating_ip
from openstack.network.v2 import vpn_ipsec_site_connection as sdk_ipsec_conn
from openstack.network.v2 import vpn_service as sdk_vpn_service

from ceilometer import keystone_client


DOMAIN_DEFAULT = ks_domains.Domain(manager=None, info={
    'id': 'default', 'name': 'Default', 'enabled': True})
DOMAIN_DEFAULT_ceilo = keystone_client.Domain(
    id='default', name='Default', is_enabled=True)
DOMAIN_DEFAULT_sdk = sdk_domain.Domain(
    connection=None,
    id='default', name='Default',
    is_enabled=True)

DOMAIN_HEAT = ks_domains.Domain(manager=None, info={
    'id': '2f42ab40b7ad4140815ef830d816a16c', 'name': 'heat', 'enabled': True,
})
DOMAIN_HEAT_ceilo = keystone_client.Domain(
    id='2f42ab40b7ad4140815ef830d816a16c', name='heat', is_enabled=True)
DOMAIN_HEAT_sdk = sdk_domain.Domain(
    connection=None,
    id='2f42ab40b7ad4140815ef830d816a16c', name='heat',
    is_enabled=True)

DOMAIN_DISABLED = ks_domains.Domain(manager=None, info={
    'id': 'disabled-domain', 'name': 'Disabled', 'enabled': False})
DOMAIN_DISABLED_ceilo = keystone_client.Domain(
    id='disabled-domain', name='Disabled', is_enabled=False)
DOMAIN_DISABLED_sdk = sdk_domain.Domain(
    connection=None,
    id='disabled-domain', name='Disabled',
    is_enabled=False)

PROJECT_ADMIN = ks_projects.Project(manager=None, info={
    'id': '2ce92449a23145ef9c539f3327960ce3', 'name': 'admin',
    'parent_id': 'default', 'domain_id': 'default', 'is_domain': False,
    'enabled': True})
PROJECT_ADMIN_ceilo = keystone_client.Project(
    id='2ce92449a23145ef9c539f3327960ce3', name='admin', parent_id='default',
    domain_id='default', is_domain=False, is_enabled=True)
PROJECT_ADMIN_sdk = sdk_project.Project(
    connection=None,
    id='2ce92449a23145ef9c539f3327960ce3', name='admin',
    parent_id='default', domain_id='default',
    is_domain=False, is_enabled=True)

PROJECT_SERVICE = ks_projects.Project(manager=None, info={
    'id': 'a2d42c23-d518-46b6-96ab-3fba2e146859', 'name': 'service',
    'parent_id': 'default', 'domain_id': 'default', 'is_domain': False,
    'enabled': True})
PROJECT_SERVICE_ceilo = keystone_client.Project(
    id='a2d42c23-d518-46b6-96ab-3fba2e146859', name='service',
    parent_id='default', domain_id='default', is_domain=False, is_enabled=True)
PROJECT_SERVICE_sdk = sdk_project.Project(
    connection=None,
    id='a2d42c23-d518-46b6-96ab-3fba2e146859', name='service',
    domain_id='default', parent_id='default',
    is_domain=False, is_enabled=True)

PROJECT_DEMO = ks_projects.Project(manager=None, info={
    'id': '57d96b9af18d43bb9d047f436279b0be', 'name': 'demo',
    'parent_id': 'default',
    'domain_id': '2f42ab40b7ad4140815ef830d816a16c',
    'is_domain': False, 'enabled': True})
PROJECT_DEMO_ceilo = keystone_client.Project(
    id='57d96b9af18d43bb9d047f436279b0be', name='demo',
    parent_id='default', domain_id='2f42ab40b7ad4140815ef830d816a16c',
    is_domain=False, is_enabled=True)
PROJECT_DEMO_sdk = sdk_project.Project(
    connection=None,
    id='57d96b9af18d43bb9d047f436279b0be', name='demo',
    domain_id='2f42ab40b7ad4140815ef830d816a16c', parent_id='default',
    is_domain=False, is_enabled=True)

PROJECT_DISABLED = ks_projects.Project(manager=None, info={
    'id': 'disabled-project', 'name': 'disabled',
    'parent_id': 'default', 'domain_id': 'default', 'is_domain': False,
    'enabled': False})
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
DEFAULT_PROJECTS = [
    PROJECT_ADMIN, PROJECT_SERVICE, PROJECT_DEMO, PROJECT_DISABLED]
DEFAULT_PROJECTS_ceilo = [
    PROJECT_ADMIN_ceilo, PROJECT_SERVICE_ceilo,
    PROJECT_DEMO_ceilo, PROJECT_DISABLED_ceilo]
DEFAULT_PROJECTS_sdk = [
    PROJECT_ADMIN_sdk, PROJECT_SERVICE_sdk,
    PROJECT_DEMO_sdk, PROJECT_DISABLED_sdk]

DEFAULT_DOMAINS = [DOMAIN_HEAT, DOMAIN_DEFAULT]
DEFAULT_DOMAINS_ceilo = [DOMAIN_HEAT_ceilo, DOMAIN_DEFAULT_ceilo]
DEFAULT_DOMAINS_sdk = [DOMAIN_HEAT_sdk, DOMAIN_DEFAULT_sdk]


class FakeDomainManager:
    """Fake keystoneclient DomainManager."""

    def __init__(self, domains=None):
        self._domains = domains if domains is not None else []

    def list(self, **filters):
        if not filters:
            return self._domains
        return [d for d in self._domains
                if all(getattr(d, k, None) == v for k, v in filters.items())]

    def find(self, name=None, **kwargs):
        filters = dict(kwargs)
        if name is not None:
            filters['name'] = name
        found = self.list(**filters)
        if len(found) > 1:
            raise ks_exceptions.NoUniqueMatch
        if found:
            return found[0]
        raise ka_exceptions.NotFound(
            404, "No Domain matching %s." % filters)


class FakeProjectManager:
    """Fake keystoneclient ProjectManager."""

    def __init__(self, projects=None):
        self._projects = projects if projects is not None else []

    def list(self, domain=None, **filters):
        if domain is None and filters == {}:
            return self._projects

        projects = self._projects
        if domain:
            domain_id = getattr(domain, 'id', domain)
            projects = [p for p in projects if p.domain_id == domain_id]

        if filters:
            for k, v in filters.items():
                projects = [p for p in projects if getattr(p, k, None) == v]

        return projects

    def find(self, name=None, domain_id=None, **kwargs):
        filters = dict(kwargs)
        if name is not None:
            filters['name'] = name
        found = self.list(domain_id, **filters)
        if len(found) > 1:
            raise ks_exceptions.NoUniqueMatch
        if found:
            return found[0]
        raise ka_exceptions.NotFound(
            404, "No Project matching %s." % filters)


class FakeKeystoneClient:
    """Fake keystoneclient.v3.client.Client for testing."""

    def __init__(self, projects=None, domains=None):
        if projects is None:
            projects = DEFAULT_PROJECTS
        if domains is None:
            domains = DEFAULT_DOMAINS
        self.auth_token = 'fake_token'
        self.projects = FakeProjectManager(projects)
        self.domains = FakeDomainManager(domains)
        self.session = None


#####################
# SDK Fakes
#####################


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


class FakeConnection:
    """Fake connection object for testing."""

    def __init__(self, session=None, domains=None, projects=None):
        """Initialize FakeConnection.

        :param projects: Optional list of SDK Project objects. Defaults to the
            class-level SDK_PROJECT_* fixtures.
        :param domains: Optional list of SDK Domain objects. Defaults to the
            class-level DOMAIN_* fixtures.
        """

        self.network = FakeSDKNetworkClient()
        self.session = session or FakeSession()
        # Don't use a short-circuit or here. The explicit check for None is
        # needed since [] is falsey, but is a valid input e.g. to create a
        # connection with no projects
        self._domains = domains if domains is not None else DEFAULT_DOMAINS_sdk
        self._projects = (
            projects if projects is not None else DEFAULT_PROJECTS_sdk)

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

VOLUME = cinder_volumes.Volume(manager=None, info={
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
SNAPSHOT = cinder_snapshots.Snapshot(manager=None, info={
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
BACKUP = cinder_backups.VolumeBackup(manager=None, info={
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
POOL_LVM = cinder_pools.Pool(manager=None, info={
    'name': 'localhost.localdomain@lvmdriver-1#lvmdriver-1',
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
})

POOL_CEPH = cinder_pools.Pool(manager=None, info={
    'name': 'cinder-3ceee-volume-ceph-0@ceph#ceph',
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
})
SERVICE_CINDER_VOLUME = cinder_services.Service(manager=None, info={
    'binary': 'cinder-volume',
    'host': 'devstack',
    'zone': 'nova',
    'status': 'enabled',
    'state': 'up'})
SERVICE_CINDER_SCHED = cinder_services.Service(manager=None, info={
    'binary': 'cinder-scheduler',
    'host': 'devstack',
    'zone': 'nova',
    'status': 'enabled',
    'state': 'up'})
SERVICE_CINDER_BACKUP = cinder_services.Service(manager=None, info={
    'binary': 'cinder-backup',
    'host': 'devstack',
    'zone': 'nova',
    'status': 'enabled',
    'state': 'down'})

VOLUME_LIST = [VOLUME]
SNAPSHOT_LIST = [SNAPSHOT]
BACKUP_LIST = [BACKUP]
POOL_LIST = [POOL_LVM, POOL_CEPH]
SERVICE_LIST = [
    SERVICE_CINDER_VOLUME, SERVICE_CINDER_SCHED, SERVICE_CINDER_BACKUP]


class FakeVolumeManager:
    """Fake cinderclient VolumeManager."""

    def __init__(self, volumes=None):
        self._volumes = volumes if volumes is not None else VOLUME_LIST

    def list(self, search_opts=None):
        return self._volumes


class FakeSnapshotManager:
    """Fake cinderclient SnapshotManager."""

    def __init__(self, snapshots=None):
        self._snapshots = snapshots if snapshots is not None else SNAPSHOT_LIST

    def list(self, search_opts=None):
        return self._snapshots


class FakeBackupManager:
    """Fake cinderclient BackupManager."""

    def __init__(self, backups=None):
        self._backups = backups if backups is not None else BACKUP_LIST

    def list(self, search_opts=None):
        return self._backups


class FakePoolManager:
    """Fake cinderclient PoolManager."""

    def __init__(self, pools=None):
        self._pools = pools if pools is not None else POOL_LIST

    def list(self, detailed=False):
        return self._pools


class FakeServiceManager:
    """Fake cinderclient ServiceManager."""

    def __init__(self, services=None):
        self._services = services if services is not None else SERVICE_LIST

    def list(self):
        return self._services


class FakeCinderClient:
    """Fake cinderclient.client.Client for testing."""

    def __init__(self, volumes=None, snapshots=None, backups=None, pools=None,
                 services=None):
        self.volumes = FakeVolumeManager(volumes)
        self.volume_snapshots = FakeSnapshotManager(snapshots)
        self.backups = FakeBackupManager(backups)
        self.pools = FakePoolManager(pools)
        self.services = FakeServiceManager(services)
