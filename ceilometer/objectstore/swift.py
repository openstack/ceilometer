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

import abc

from keystoneclient.v2_0 import client as ksclient
from swiftclient import client as swift

from ceilometer import plugin
from ceilometer import counter
from ceilometer.openstack.common import cfg
from ceilometer.openstack.common import timeutils
from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('reseller_prefix',
               default='AUTH_',
               help="Swift reseller prefix. Must be on par with "\
                   "reseller_prefix in proxy-server.conf."),
]

cfg.CONF.register_opts(OPTS)


class _Base(plugin.PollsterBase):

    __metaclass__ = abc.ABCMeta

    @staticmethod
    @abc.abstractmethod
    def iter_accounts():
        """Iterate over all accounts, yielding (tenant_id, stats) tuples."""

    def get_counters(self, manager, context):
        for tenant, account in self.iter_accounts():
            yield counter.Counter(
                name='storage.objects',
                type=counter.TYPE_GAUGE,
                volume=int(account['x-account-object-count']),
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                timestamp=timeutils.isotime(),
                resource_metadata=None,
            )
            yield counter.Counter(
                name='storage.objects.size',
                type=counter.TYPE_GAUGE,
                volume=int(account['x-account-bytes-used']),
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                timestamp=timeutils.isotime(),
                resource_metadata=None,
            )
            yield counter.Counter(
                name='storage.objects.containers',
                type=counter.TYPE_GAUGE,
                volume=int(account['x-account-container-count']),
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                timestamp=timeutils.isotime(),
                resource_metadata=None,
            )


class SwiftPollster(_Base):
    """Iterate over all accounts, using keystone.
    """

    @staticmethod
    def iter_accounts():
        ks = ksclient.Client(username=cfg.CONF.os_username,
                             password=cfg.CONF.os_password,
                             tenant_name=cfg.CONF.os_tenant_name,
                             auth_url=cfg.CONF.os_auth_url)
        endpoint = ks.service_catalog.url_for(service_type='object-store',
                                              endpoint_type='adminURL')
        base_url = '%s/v1/%s' % (endpoint, cfg.CONF.reseller_prefix)
        for t in ks.tenants.list():
            yield (t.id, swift.head_account('%s%s' % (base_url, t.id),
                                            ks.auth_token))
