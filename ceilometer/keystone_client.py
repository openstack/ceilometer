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


from keystoneclient import discover as ks_discover
from keystoneclient import exceptions as ks_exception
from keystoneclient import session as ks_session
from keystoneclient.v2_0 import client as ks_client
from keystoneclient.v3 import client as ks_client_v3
from oslo_config import cfg

cfg.CONF.import_group('service_credentials', 'ceilometer.service')
cfg.CONF.import_opt('http_timeout', 'ceilometer.service')


def get_client():
    return ks_client.Client(
        username=cfg.CONF.service_credentials.os_username,
        password=cfg.CONF.service_credentials.os_password,
        tenant_id=cfg.CONF.service_credentials.os_tenant_id,
        tenant_name=cfg.CONF.service_credentials.os_tenant_name,
        cacert=cfg.CONF.service_credentials.os_cacert,
        auth_url=cfg.CONF.service_credentials.os_auth_url,
        region_name=cfg.CONF.service_credentials.os_region_name,
        insecure=cfg.CONF.service_credentials.insecure,
        timeout=cfg.CONF.http_timeout,)


def get_v3_client(trust_id=None):
    """Return a client for keystone v3 endpoint, optionally using a trust."""
    auth_url = cfg.CONF.service_credentials.os_auth_url
    try:
        auth_url_noneversion = auth_url.replace('/v2.0', '/')
        discover = ks_discover.Discover(auth_url=auth_url_noneversion)
        v3_auth_url = discover.url_for('3.0')
        if v3_auth_url:
            auth_url = v3_auth_url
        else:
            auth_url = auth_url
    except Exception:
        auth_url = auth_url.replace('/v2.0', '/v3')
    return ks_client_v3.Client(
        username=cfg.CONF.service_credentials.os_username,
        password=cfg.CONF.service_credentials.os_password,
        cacert=cfg.CONF.service_credentials.os_cacert,
        auth_url=auth_url,
        region_name=cfg.CONF.service_credentials.os_region_name,
        insecure=cfg.CONF.service_credentials.insecure,
        timeout=cfg.CONF.http_timeout,
        trust_id=trust_id)


def create_trust_id(trustor_user_id, trustor_project_id, roles, auth_plugin):
    """Create a new trust using the ceilometer service user."""
    admin_client = get_v3_client()

    trustee_user_id = admin_client.auth_ref.user_id

    session = ks_session.Session.construct({
        'cacert': cfg.CONF.service_credentials.os_cacert,
        'insecure': cfg.CONF.service_credentials.insecure})

    client = ks_client_v3.Client(session=session, auth=auth_plugin)

    trust = client.trusts.create(trustor_user=trustor_user_id,
                                 trustee_user=trustee_user_id,
                                 project=trustor_project_id,
                                 impersonation=True,
                                 role_names=roles)
    return trust.id


def delete_trust_id(trust_id, auth_plugin):
    """Delete a trust previously setup for the ceilometer user."""
    session = ks_session.Session.construct({
        'cacert': cfg.CONF.service_credentials.os_cacert,
        'insecure': cfg.CONF.service_credentials.insecure})

    client = ks_client_v3.Client(session=session, auth=auth_plugin)
    try:
        client.trusts.delete(trust_id)
    except ks_exception.NotFound:
        pass
