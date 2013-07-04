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

from oslo.config import cfg
from swiftclient import client as swift
from keystoneclient import exceptions

from ceilometer import counter
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer import plugin

from urlparse import urljoin


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
    CACHE_KEY_HEAD = 'swift.head_account'

    def _iter_accounts(self, ksclient, cache):
        if self.CACHE_KEY_TENANT not in cache:
            cache[self.CACHE_KEY_TENANT] = ksclient.tenants.list()
        if self.CACHE_KEY_HEAD not in cache:
            cache[self.CACHE_KEY_HEAD] = list(self._get_account_info(ksclient,
                                                                     cache))
        return iter(cache['swift.head_account'])

    def _get_account_info(self, ksclient, cache):
        try:
            endpoint = ksclient.service_catalog.url_for(
                service_type='object-store',
                endpoint_type='adminURL')
        except exceptions.EndpointNotFound:
            LOG.debug(_("Swift endpoint not found"))
            raise StopIteration()

        for t in cache['tenants']:
            yield (t.id, swift.head_account(self._neaten_url(endpoint, t.id),
                                            ksclient.auth_token))

    @staticmethod
    def _neaten_url(endpoint, tenant_id):
        """Transform the registered url to standard and valid format.
        """

        path = 'v1/' + cfg.CONF.reseller_prefix + tenant_id

        # remove the tail '/' of the endpoint.
        if endpoint.endswith('/'):
            endpoint = endpoint[:-1]

        return urljoin(endpoint, path)


class ObjectsPollster(_Base):
    """Iterate over all accounts, using keystone.
    """

    @staticmethod
    def get_counter_names():
        return ['storage.objects']

    def get_counters(self, manager, cache):
        for tenant, account in self._iter_accounts(manager.keystone, cache):
            yield counter.Counter(
                name='storage.objects',
                type=counter.TYPE_GAUGE,
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

    @staticmethod
    def get_counter_names():
        return ['storage.objects.size']

    def get_counters(self, manager, cache):
        for tenant, account in self._iter_accounts(manager.keystone, cache):
            yield counter.Counter(
                name='storage.objects.size',
                type=counter.TYPE_GAUGE,
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

    @staticmethod
    def get_counter_names():
        return ['storage.objects.containers']

    def get_counters(self, manager, cache):
        for tenant, account in self._iter_accounts(manager.keystone, cache):
            yield counter.Counter(
                name='storage.objects.containers',
                type=counter.TYPE_GAUGE,
                volume=int(account['x-account-container-count']),
                unit='container',
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                timestamp=timeutils.isotime(),
                resource_metadata=None,
            )
