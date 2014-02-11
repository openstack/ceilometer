# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance
#
# Author: Guillaume Pernot <gpernot@praksys.org>
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
import six.moves.urllib.parse as urlparse

from keystoneclient import exceptions
from oslo.config import cfg
from swiftclient import client as swift

from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer import plugin
from ceilometer import sample


LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('reseller_prefix',
               default='AUTH_',
               help="Swift reseller prefix. Must be on par with "
               "reseller_prefix in proxy-server.conf."),
]

cfg.CONF.register_opts(OPTS)


class _Base(plugin.PollsterBase):

    CACHE_KEY_TENANT = 'tenants'
    METHOD = 'head'

    @property
    def CACHE_KEY_METHOD(self):
        return 'swift.%s_account' % self.METHOD

    def _iter_accounts(self, ksclient, cache):
        if self.CACHE_KEY_TENANT not in cache:
            cache[self.CACHE_KEY_TENANT] = ksclient.tenants.list()
        if self.CACHE_KEY_METHOD not in cache:
            cache[self.CACHE_KEY_METHOD] = list(self._get_account_info(
                                                ksclient, cache))
        return iter(cache[self.CACHE_KEY_METHOD])

    def _get_account_info(self, ksclient, cache):
        try:
            endpoint = ksclient.service_catalog.url_for(
                service_type='object-store',
                endpoint_type=cfg.CONF.service_credentials.os_endpoint_type)
        except exceptions.EndpointNotFound:
            LOG.debug(_("Swift endpoint not found"))
            raise StopIteration()

        for t in cache[self.CACHE_KEY_TENANT]:
            api_method = '%s_account' % self.METHOD
            yield (t.id, getattr(swift, api_method)
                                (self._neaten_url(endpoint, t.id),
                                 ksclient.auth_token))

    @staticmethod
    def _neaten_url(endpoint, tenant_id):
        """Transform the registered url to standard and valid format.
        """
        return urlparse.urljoin(endpoint,
                                '/v1/' + cfg.CONF.reseller_prefix + tenant_id)


class ObjectsPollster(_Base):
    """Iterate over all accounts, using keystone.
    """

    def get_samples(self, manager, cache, resources=[]):
        for tenant, account in self._iter_accounts(manager.keystone, cache):
            yield sample.Sample(
                name='storage.objects',
                type=sample.TYPE_GAUGE,
                volume=int(account['x-account-object-count']),
                unit='object',
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                timestamp=timeutils.isotime(),
                resource_metadata=None,
            )


class ObjectsSizePollster(_Base):
    """Iterate over all accounts, using keystone.
    """

    def get_samples(self, manager, cache, resources=[]):
        for tenant, account in self._iter_accounts(manager.keystone, cache):
            yield sample.Sample(
                name='storage.objects.size',
                type=sample.TYPE_GAUGE,
                volume=int(account['x-account-bytes-used']),
                unit='B',
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                timestamp=timeutils.isotime(),
                resource_metadata=None,
            )


class ObjectsContainersPollster(_Base):
    """Iterate over all accounts, using keystone.
    """

    def get_samples(self, manager, cache, resources=[]):
        for tenant, account in self._iter_accounts(manager.keystone, cache):
            yield sample.Sample(
                name='storage.objects.containers',
                type=sample.TYPE_GAUGE,
                volume=int(account['x-account-container-count']),
                unit='container',
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                timestamp=timeutils.isotime(),
                resource_metadata=None,
            )


class ContainersObjectsPollster(_Base):
    """Get info about containers using Swift API
    """

    METHOD = 'get'

    def get_samples(self, manager, cache, resources=[]):
        for project, account in self._iter_accounts(manager.keystone, cache):
            containers_info = account[1]
            for container in containers_info:
                yield sample.Sample(
                    name='storage.containers.objects',
                    type=sample.TYPE_GAUGE,
                    volume=int(container['count']),
                    unit='object',
                    user_id=None,
                    project_id=project,
                    resource_id=project + '/' + container['name'],
                    timestamp=timeutils.isotime(),
                    resource_metadata=None,
                )


class ContainersSizePollster(_Base):
    """Get info about containers using Swift API
    """

    METHOD = 'get'

    def get_samples(self, manager, cache, resources=[]):
        for project, account in self._iter_accounts(manager.keystone, cache):
            containers_info = account[1]
            for container in containers_info:
                yield sample.Sample(
                    name='storage.containers.objects.size',
                    type=sample.TYPE_GAUGE,
                    volume=int(container['bytes']),
                    unit='B',
                    user_id=None,
                    project_id=project,
                    resource_id=project + '/' + container['name'],
                    timestamp=timeutils.isotime(),
                    resource_metadata=None,
                )
