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
from oslo_config import cfg

DEFAULT_GROUP = "service_credentials"

# List of group that can set auth_section to use a different
# credentials section
OVERRIDABLE_GROUPS = ['dispatcher_gnocchi', 'zaqar']


def get_session(conf, requests_session=None, group=None, timeout=None):

    """Get a ceilometer service credentials auth session."""
    group = group or DEFAULT_GROUP
    auth_plugin = ka_loading.load_auth_from_conf_options(conf, group)
    kwargs = {'auth': auth_plugin, 'session': requests_session}
    if timeout is not None:
        kwargs['timeout'] = timeout
    session = ka_loading.load_session_from_conf_options(conf, group, **kwargs)
    return session


def get_client(conf, trust_id=None, requests_session=None,
               group=DEFAULT_GROUP):
    """Return a client for keystone v3 endpoint, optionally using a trust."""
    session = get_session(conf, requests_session=requests_session, group=group)
    return ks_client_v3.Client(session=session, trust_id=trust_id,
                               region_name=conf[group].region_name)


def get_service_catalog(client):
    return client.session.auth.get_access(client.session).service_catalog


def get_auth_token(client):
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
