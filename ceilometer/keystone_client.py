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

import os

from keystoneauth1 import loading as ka_loading
from keystoneclient.v3 import client as ks_client_v3
from openstack import connection
from oslo_config import cfg

DEFAULT_GROUP = "service_credentials"

# List of group that can set auth_section to use a different
# credentials section
OVERRIDABLE_GROUPS = ['gnocchi', 'zaqar']


class Client:
    """Client for retrieving keystone resources.

    Accesses Projects and Domains from keystone service.
    """

    def __init__(self, session, **kwargs):
        """Instantiate a Client that can access keystone.

        :param session: A ``keystoneauth1.session.Session`` instance used for
            all HTTP communication.
        :param kwargs: Additional keyword arguments forwarded verbatim to
            ``keystoneclient.v3.client.Client`` (e.g. ``interface``,
            ``region_name``).

        """
        self._ks_client = ks_client_v3.Client(
            session=session, **kwargs)
        self.domains = self._ks_client.domains
        self.projects = self._ks_client.projects
        self.session = session

    def find_project(self, **kwargs):
        """Find a single project matching the given attribute filters.

        Delegates to ``keystoneclient.v3.projects.ProjectManager.find``.

        :param kwargs: Attribute filters used to locate the project, e.g.
            ``name='myproject'``, ``domain_id='<uuid>'``. All keyword
            arguments are forwarded to the underlying ``find`` call.
        :returns: A single ``keystoneclient.v3.projects.Project`` resource
            object whose attributes match all supplied filters.
        :raises keystoneauth1.exceptions.NotFound: if no project matches
            the filters.
        :raises keystoneclient.exceptions.NoUniqueMatch: if more than one
            project matches the filters.
        """
        return self.projects.find(**kwargs)

    def list_projects(self, domain, **filters):
        """List projects within a domain, with optional attribute filters.

        Delegates to ``keystoneclient.v3.projects.ProjectManager.list``.

        :param domain: The domain whose projects should be returned. Accepts
            either a domain ID string or a
            ``keystoneclient.v3.domains.Domain`` object.
        :param filters: Optional keyword arguments used as additional query
            filters, e.g. ``enabled=True`` to restrict results to enabled
            projects.
        :returns: A list of ``keystoneclient.v3.projects.Project`` resource
            objects belonging to the given domain. Returns an empty list when
            no projects match.
        """
        return self.projects.list(domain, **filters)

    def find_domain(self, **kwargs):
        """Find a single domain matching the given attribute filters.

        Delegates to ``keystoneclient.v3.domains.DomainManager.find``.

        :param kwargs: Attribute filters used to locate the domain, e.g.
            ``name='Default'``.  All keyword arguments are forwarded to the
            underlying ``find`` call.
        :returns: A single ``keystoneclient.v3.domains.Domain`` resource object
            whose attributes match all supplied filters.
        :raises keystoneauth1.exceptions.NotFound: if no domain matches
            the filters.
        :raises keystoneclient.exceptions.NoUniqueMatch: if more than one
            domain matches the filters.
        """
        return self.domains.find(**kwargs)

    def list_domains(self, **filters):
        """List all domains, with optional attribute filters.

        Delegates to ``keystoneclient.v3.domains.DomainManager.list``.

        :param filters: Optional keyword arguments forwarded to
            ``DomainManager.list`` as query filters, e.g. ``enabled=True``
            to restrict results to enabled domains.
        :returns: A list of ``keystoneclient.v3.domains.Domain`` resource
            objects.  Returns an empty list when no domains match.
        """
        return self.domains.list(**filters)


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
