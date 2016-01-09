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

from keystoneauth1 import exceptions as ka_exception
from keystoneauth1 import identity as ka_identity
from keystoneauth1 import loading as ka_loading
from keystoneclient.v3 import client as ks_client_v3
from oslo_config import cfg
from oslo_log import log

LOG = log.getLogger(__name__)

CFG_GROUP = "service_credentials"


def get_session(requests_session=None):
    """Get a ceilometer service credentials auth session."""
    auth_plugin = ka_loading.load_auth_from_conf_options(cfg.CONF, CFG_GROUP)
    session = ka_loading.load_session_from_conf_options(
        cfg.CONF, CFG_GROUP, auth=auth_plugin, session=requests_session
    )
    return session


def get_client(trust_id=None, requests_session=None):
    """Return a client for keystone v3 endpoint, optionally using a trust."""
    session = get_session(requests_session=requests_session)
    return ks_client_v3.Client(session=session, trust_id=trust_id)


def get_service_catalog(client):
    return client.session.auth.get_access(client.session).service_catalog


def get_auth_token(client):
    return client.session.auth.get_access(client.session).auth_token


def get_client_on_behalf_user(auth_plugin, trust_id=None,
                              requests_session=None):
    """Return a client for keystone v3 endpoint, optionally using a trust."""
    session = ka_loading.load_session_from_conf_options(
        cfg.CONF, CFG_GROUP, auth=auth_plugin, session=requests_session
    )
    return ks_client_v3.Client(session=session, trust_id=trust_id)


def create_trust_id(trustor_user_id, trustor_project_id, roles, auth_plugin):
    """Create a new trust using the ceilometer service user."""
    admin_client = get_client()
    trustee_user_id = admin_client.auth_ref.user_id

    client = get_client_on_behalf_user(auth_plugin=auth_plugin)
    trust = client.trusts.create(trustor_user=trustor_user_id,
                                 trustee_user=trustee_user_id,
                                 project=trustor_project_id,
                                 impersonation=True,
                                 role_names=roles)
    return trust.id


def delete_trust_id(trust_id, auth_plugin):
    """Delete a trust previously setup for the ceilometer user."""
    client = get_client_on_behalf_user(auth_plugin=auth_plugin)
    try:
        client.trusts.delete(trust_id)
    except ka_exception.NotFound:
        pass


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

cfg.CONF.register_cli_opts(CLI_OPTS, group=CFG_GROUP)


def register_keystoneauth_opts(conf):
    ka_loading.register_auth_conf_options(conf, CFG_GROUP)
    ka_loading.register_session_conf_options(
        conf, CFG_GROUP,
        deprecated_opts={'cacert': [
            cfg.DeprecatedOpt('os-cacert', group=CFG_GROUP),
            cfg.DeprecatedOpt('os-cacert', group="DEFAULT")]
        })
    conf.set_default("auth_type", default="password-ceilometer-legacy",
                     group=CFG_GROUP)


def setup_keystoneauth(conf):
    if conf[CFG_GROUP].auth_type == "password-ceilometer-legacy":
        LOG.warning("Value 'password-ceilometer-legacy' for '[%s]/auth_type' "
                    "is deprecated. And will be removed in Ceilometer 7.0. "
                    "Use 'password' instead.",
                    CFG_GROUP)

    ka_loading.load_auth_from_conf_options(conf, CFG_GROUP)


class LegacyCeilometerKeystoneLoader(ka_loading.BaseLoader):
    @property
    def plugin_class(self):
        return ka_identity.V2Password

    def get_options(self):
        options = super(LegacyCeilometerKeystoneLoader, self).get_options()
        options.extend([
            ka_loading.Opt(
                'os-username',
                default=os.environ.get('OS_USERNAME', 'ceilometer'),
                help='User name to use for OpenStack service access.'),
            ka_loading.Opt(
                'os-password',
                secret=True,
                default=os.environ.get('OS_PASSWORD', 'admin'),
                help='Password to use for OpenStack service access.'),
            ka_loading.Opt(
                'os-tenant-id',
                default=os.environ.get('OS_TENANT_ID', ''),
                help='Tenant ID to use for OpenStack service access.'),
            ka_loading.Opt(
                'os-tenant-name',
                default=os.environ.get('OS_TENANT_NAME', 'admin'),
                help='Tenant name to use for OpenStack service access.'),
            ka_loading.Opt(
                'os-auth-url',
                default=os.environ.get('OS_AUTH_URL',
                                       'http://localhost:5000/v2.0'),
                help='Auth URL to use for OpenStack service access.'),
        ])
        return options

    def load_from_options(self, **kwargs):
        options_map = {
            'os_auth_url': 'auth_url',
            'os_username': 'username',
            'os_password': 'password',
            'os_tenant_name': 'tenant_name',
            'os_tenant_id': 'tenant_id',
        }
        identity_kwargs = dict((options_map[o.dest],
                                kwargs.get(o.dest) or o.default)
                               for o in self.get_options()
                               if o.dest in options_map)
        return self.plugin_class(**identity_kwargs)
