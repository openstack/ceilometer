#
# Copyright 2012 eNovance
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
"""Common code for working with object stores
"""

from __future__ import absolute_import

from keystoneauth1 import exceptions
from oslo_config import cfg
from oslo_log import log
import six.moves.urllib.parse as urlparse
from swiftclient import client as swift
from swiftclient.exceptions import ClientException

from ceilometer.agent import plugin_base
from ceilometer import keystone_client
from ceilometer import sample


LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('reseller_prefix',
               default='AUTH_',
               help="Swift reseller prefix. Must be on par with "
               "reseller_prefix in proxy-server.conf."),
]

SERVICE_OPTS = [
    cfg.StrOpt('swift',
               default='object-store',
               help='Swift service type.'),
]


class _Base(plugin_base.PollsterBase):

    METHOD = 'head'
    _ENDPOINT = None

    @property
    def default_discovery(self):
        return 'tenant'

    @property
    def CACHE_KEY_METHOD(self):
        return 'swift.%s_account' % self.METHOD

    @staticmethod
    def _get_endpoint(conf, ksclient):
        # we store the endpoint as a base class attribute, so keystone is
        # only ever called once
        if _Base._ENDPOINT is None:
            try:
                creds = conf.service_credentials
                _Base._ENDPOINT = keystone_client.get_service_catalog(
                    ksclient).url_for(
                        service_type=conf.service_types.swift,
                        interface=creds.interface,
                        region_name=creds.region_name)
            except exceptions.EndpointNotFound as e:
                LOG.info("Swift endpoint not found: %s", e)
        return _Base._ENDPOINT

    def _iter_accounts(self, ksclient, cache, tenants):
        if self.CACHE_KEY_METHOD not in cache:
            cache[self.CACHE_KEY_METHOD] = list(self._get_account_info(
                ksclient, tenants))
        return iter(cache[self.CACHE_KEY_METHOD])

    def _get_account_info(self, ksclient, tenants):
        endpoint = self._get_endpoint(self.conf, ksclient)
        if not endpoint:
            raise StopIteration()

        swift_api_method = getattr(swift, '%s_account' % self.METHOD)
        for t in tenants:
            try:
                yield (t.id, swift_api_method(
                    self._neaten_url(endpoint, t.id,
                                     self.conf.reseller_prefix),
                    keystone_client.get_auth_token(ksclient)))
            except ClientException as e:
                if e.http_status == 404:
                    LOG.warning("Swift tenant id %s not found.", t.id)
                else:
                    raise e

    @staticmethod
    def _neaten_url(endpoint, tenant_id, reseller_prefix):
        """Transform the registered url to standard and valid format."""
        return urlparse.urljoin(endpoint.split('/v1')[0].rstrip('/') + '/',
                                'v1/' + reseller_prefix + tenant_id)


class ObjectsPollster(_Base):
    """Collect the total objects count for each project"""
    def get_samples(self, manager, cache, resources):
        tenants = resources
        for tenant, account in self._iter_accounts(manager.keystone,
                                                   cache, tenants):
            yield sample.Sample(
                name='storage.objects',
                type=sample.TYPE_GAUGE,
                volume=int(account['x-account-object-count']),
                unit='object',
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                resource_metadata=None,
            )


class ObjectsSizePollster(_Base):
    """Collect the total objects size of each project"""
    def get_samples(self, manager, cache, resources):
        tenants = resources
        for tenant, account in self._iter_accounts(manager.keystone,
                                                   cache, tenants):
            yield sample.Sample(
                name='storage.objects.size',
                type=sample.TYPE_GAUGE,
                volume=int(account['x-account-bytes-used']),
                unit='B',
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                resource_metadata=None,
            )


class ObjectsContainersPollster(_Base):
    """Collect the container count for each project"""
    def get_samples(self, manager, cache, resources):
        tenants = resources
        for tenant, account in self._iter_accounts(manager.keystone,
                                                   cache, tenants):
            yield sample.Sample(
                name='storage.objects.containers',
                type=sample.TYPE_GAUGE,
                volume=int(account['x-account-container-count']),
                unit='container',
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                resource_metadata=None,
            )


class ContainersObjectsPollster(_Base):
    """Collect the objects count per container for each project"""

    METHOD = 'get'

    def get_samples(self, manager, cache, resources):
        tenants = resources
        for tenant, account in self._iter_accounts(manager.keystone,
                                                   cache, tenants):
            containers_info = account[1]
            for container in containers_info:
                yield sample.Sample(
                    name='storage.containers.objects',
                    type=sample.TYPE_GAUGE,
                    volume=int(container['count']),
                    unit='object',
                    user_id=None,
                    project_id=tenant,
                    resource_id=tenant + '/' + container['name'],
                    resource_metadata=None,
                )


class ContainersSizePollster(_Base):
    """Collect the total objects size per container for each project"""

    METHOD = 'get'

    def get_samples(self, manager, cache, resources):
        tenants = resources
        for tenant, account in self._iter_accounts(manager.keystone,
                                                   cache, tenants):
            containers_info = account[1]
            for container in containers_info:
                yield sample.Sample(
                    name='storage.containers.objects.size',
                    type=sample.TYPE_GAUGE,
                    volume=int(container['bytes']),
                    unit='B',
                    user_id=None,
                    project_id=tenant,
                    resource_id=tenant + '/' + container['name'],
                    resource_metadata=None,
                )
