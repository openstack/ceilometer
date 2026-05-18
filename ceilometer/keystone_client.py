#
# Copyright 2015 eNovance <licensing@enovance.com>
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

import dataclasses
import os

from keystoneauth1 import loading as ka_loading
from openstack import connection
from oslo_config import cfg

from ceilometer import exceptions as ceilo_exc


DEFAULT_GROUP = "service_credentials"

# List of group that can set auth_section to use a different
# credentials section
OVERRIDABLE_GROUPS = ['gnocchi', 'zaqar']


@dataclasses.dataclass(frozen=True)
class Project:
    id: str
    name: str
    domain_id: str
    is_enabled: bool
    description: str = ''
    parent_id: str | None = None
    is_domain: bool = False

    @classmethod
    def from_ksclient(cls, ks_project):
        return cls(
            id=ks_project.id,
            name=ks_project.name,
            domain_id=ks_project.domain_id,
            is_enabled=ks_project.enabled,
            description=getattr(ks_project, 'description', None) or '',
            parent_id=getattr(ks_project, 'parent_id', None),
            is_domain=getattr(ks_project, 'is_domain', False),
        )

    @classmethod
    def from_openstacksdk(cls, sdk_project):
        return cls(
            id=sdk_project.id,
            name=sdk_project.name,
            domain_id=sdk_project.domain_id,
            is_enabled=sdk_project.is_enabled,
            description=sdk_project.description or '',
            parent_id=sdk_project.parent_id,
            is_domain=sdk_project.is_domain,
        )


@dataclasses.dataclass(frozen=True)
class Domain:
    id: str
    name: str
    is_enabled: bool
    description: str = ''

    @classmethod
    def from_ksclient(cls, ks_domain):
        return cls(
            id=ks_domain.id,
            name=ks_domain.name,
            is_enabled=ks_domain.enabled,
            description=getattr(ks_domain, 'description', None) or '',
        )

    @classmethod
    def from_openstacksdk(cls, sdk_domain):
        return cls(
            id=sdk_domain.id,
            name=sdk_domain.name,
            is_enabled=sdk_domain.is_enabled,
            description=sdk_domain.description or '',
        )


class Client:
    """Client for retrieving keystone resources.

    Accesses Projects and Domains from keystone service.
    """

    def __init__(self, session, **kwargs):
        """Instantiate a Client that can access keystone.

        :param session: A ``keystoneauth1.session.Session`` instance used for
            all HTTP communication.
        :param kwargs: Additional keyword arguments forwarded verbatim to
            ``openstack.connection.Connection`` (e.g. ``interface``,
            ``region_name``).

        """

        self._connection = connection.Connection(
            session=session,
            service_types={"identity"},
            **kwargs
        )
        self.session = session

    def find_project(self, **kwargs):
        """Find a single project matching the given attribute filters.

        Delegates to the OpenStack SDK connection via
        ``search_projects(name_or_id, filters, domain_id)``.

        :param kwargs: Attribute filters used to locate the project, e.g.
            ``name='myproject'``, ``domain_id='<uuid>'``. All keyword
            arguments are forwarded to the underlying SDK call.
        :returns: A single ``Project`` resource
            object whose attributes match all supplied filters.
        :raises ceilometer.exceptions.NotFound: if no project matches
            the filters.
        :raises ceilometer.exceptions.NoUniqueMatch: if more than one
            project matches the filters.
        """
        filters = dict(**kwargs)
        name_or_id = filters.pop('id', None)
        if name_or_id is None:
            name_or_id = filters.pop('name', None)
        domain_id = filters.pop('domain_id', None)
        project = self._connection.search_projects(
            name_or_id=name_or_id,
            filters=filters or None,
            domain_id=domain_id)

        if len(project) > 1:
            raise ceilo_exc.NoUniqueMatch("ClientException")
        if len(project) == 0:
            raise ceilo_exc.NotFound(
                "No matching resources found",
                f"No Project matching {dict(**kwargs)}.")
        return Project.from_openstacksdk(project[0])

    def list_projects(self, domain, **filters):
        """List projects within a domain, with optional attribute filters.

        :param domain: The domain whose projects should be returned. Accepts
            either a domain ID string or a :class:`Domain` object.
        :param filters: Optional keyword arguments used as additional query
            filters, e.g. ``enabled=True`` to restrict results to enabled
            projects.
        :returns: A list of :class:`Project` objects belonging to the given
            domain. Returns an empty list when no projects match.
        """
        # domain can be a string.
        domain_id = getattr(domain, 'id', domain)
        projects = self._connection.list_projects(
            domain_id=domain_id, filters=filters or None)
        return [Project.from_openstacksdk(p) for p in projects]

    def find_domain(self, **kwargs):
        """Find a single domain matching the given attribute filters.

        :param kwargs: Attribute filters used to locate the domain, e.g.
            ``name='Default'``.
        :returns: A single :class:`Domain` object whose attributes match all
            supplied filters.
        :raises ceilometer.exceptions.NotFound: if no domain matches
            the filters.
        :raises ceilometer.exceptions.NoUniqueMatch: if more than one
            domain matches the filters.
        """
        filters = dict(**kwargs)
        name_or_id = filters.pop('id', None)
        if name_or_id is None:
            name_or_id = filters.pop('name', None)
        domains = self._connection.search_domains(
            name_or_id=name_or_id, filters=filters or None)
        if len(domains) > 1:
            raise ceilo_exc.NoUniqueMatch("ClientException")
        if len(domains) == 0:
            raise ceilo_exc.NotFound(
                "No matching resources found",
                f"No Domain matching {dict(kwargs)}.")
        return Domain.from_openstacksdk(domains[0])

    def list_domains(self, **filters):
        """List all domains, with optional attribute filters.

        :param filters: Optional keyword arguments used as query filters,
            e.g. ``enabled=True`` to restrict results to enabled domains.
        :returns: A list of :class:`Domain` objects.
        """
        return [Domain.from_openstacksdk(d)
                for d in self._connection.list_domains(
                    filters=filters or None)]


def get_session(conf, requests_session=None, group=None, timeout=None):
    """Get a ceilometer service credentials auth session."""
    group = group or DEFAULT_GROUP
    auth_plugin = ka_loading.load_auth_from_conf_options(conf, group)
    kwargs = {'auth': auth_plugin, 'session': requests_session}
    if timeout is not None:
        kwargs['timeout'] = timeout
    session = ka_loading.load_session_from_conf_options(conf, group, **kwargs)
    return session


def get_connection(
        conf, service_type="identity",
        requests_session=None, group=DEFAULT_GROUP):
    """Get an openstacksdk connection to interact with openstack services."""
    sess = get_session(
        conf, requests_session=requests_session, group=group)

    # https://github.com/openstack/nova/blob/master/nova/utils.py#L905
    conn = connection.Connection(
        session=sess,
        oslo_conf=conf,
        service_types={service_type}
    )
    return conn


def get_client(conf, requests_session=None, group=DEFAULT_GROUP):
    """Return a client for keystone v3 endpoint."""
    session = get_session(conf, requests_session=requests_session, group=group)

    return Client(session=session,
                  interface=conf[group].interface,
                  region_name=conf[group].region_name)


def get_service_catalog(client):
    return client.session.auth.get_access(client.session).service_catalog


def url_for(
        client, service_type=None, service_name=None,
        interface=None, region_name=None):
    return get_service_catalog(client).url_for(
        service_type=service_type, service_name=service_name,
        interface=interface, region_name=region_name)


def get_urls(
        client, service_type=None, service_name=None,
        interface=None, region_name=None):
    return get_service_catalog(client).get_urls(
        service_type=service_type, service_name=service_name,
        interface=interface, region_name=region_name)


def get_auth_token(client):
    # NOTE: client.session.get_token() can be used for both
    # keystoneclient.v3.client.Client and openstack.connection.Connection
    return client.session.auth.get_access(client.session).auth_token


CLI_OPTS = [
    cfg.StrOpt('region-name',
               deprecated_group="DEFAULT",
               deprecated_name="os-region-name",
               default=os.environ.get('OS_REGION_NAME'),
               help='Region name to use for OpenStack service endpoints.'),
    cfg.StrOpt('interface',
               default=os.environ.get(
                   'OS_INTERFACE', os.environ.get('OS_ENDPOINT_TYPE',
                                                  'public')),
               deprecated_name="os-endpoint-type",
               choices=('public', 'internal', 'admin', 'auth', 'publicURL',
                        'internalURL', 'adminURL'),
               help='Type of endpoint in Identity service catalog to use for '
                    'communication with OpenStack services.'),
]


def register_keystoneauth_opts(conf):
    _register_keystoneauth_group(conf, DEFAULT_GROUP)
    for group in OVERRIDABLE_GROUPS:
        _register_keystoneauth_group(conf, group)
        conf.set_default('auth_section', DEFAULT_GROUP, group=group)


def _register_keystoneauth_group(conf, group):
    ka_loading.register_auth_conf_options(conf, group)
    ka_loading.register_session_conf_options(
        conf, group,
        deprecated_opts={'cacert': [
            cfg.DeprecatedOpt('os-cacert', group=group),
            cfg.DeprecatedOpt('os-cacert', group="DEFAULT")]
        })
    conf.register_opts(CLI_OPTS, group=group)


def post_register_keystoneauth_opts(conf):
    for group in OVERRIDABLE_GROUPS:
        if conf[group].auth_section != DEFAULT_GROUP:
            # NOTE(sileht): We register this again after the auth_section have
            # been read from the configuration file
            _register_keystoneauth_group(conf, conf[group].auth_section)
