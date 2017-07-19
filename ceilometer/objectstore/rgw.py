#
# Copyright 2015 Reliance Jio Infocomm Ltd.
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
"""Common code for working with ceph object stores
"""

from keystoneauth1 import exceptions
from oslo_config import cfg
from oslo_log import log
import six.moves.urllib.parse as urlparse

from ceilometer.agent import plugin_base
from ceilometer import keystone_client
from ceilometer import sample

LOG = log.getLogger(__name__)

SERVICE_OPTS = [
    cfg.StrOpt('radosgw',
               help='Radosgw service type.'),
]

CREDENTIAL_OPTS = [
    cfg.StrOpt('access_key',
               secret=True,
               help='Access key for Radosgw Admin.'),
    cfg.StrOpt('secret_key',
               secret=True,
               help='Secret key for Radosgw Admin.')
]


class _Base(plugin_base.PollsterBase):
    METHOD = 'bucket'
    _ENDPOINT = None

    def __init__(self, conf):
        super(_Base, self).__init__(conf)
        self.access_key = self.conf.rgw_admin_credentials.access_key
        self.secret = self.conf.rgw_admin_credentials.secret_key

    @property
    def default_discovery(self):
        return 'tenant'

    @property
    def CACHE_KEY_METHOD(self):
        return 'rgw.get_%s' % self.METHOD

    @staticmethod
    def _get_endpoint(conf, ksclient):
        # we store the endpoint as a base class attribute, so keystone is
        # only ever called once, also we assume that in a single deployment
        # we may be only deploying `radosgw` or `swift` as the object-store
        if _Base._ENDPOINT is None and conf.service_types.radosgw:
            try:
                creds = conf.service_credentials
                rgw_url = keystone_client.get_service_catalog(
                    ksclient).url_for(
                        service_type=conf.service_types.radosgw,
                        interface=creds.interface,
                        region_name=creds.region_name)
                _Base._ENDPOINT = urlparse.urljoin(rgw_url, '/admin')
            except exceptions.EndpointNotFound:
                LOG.debug("Radosgw endpoint not found")
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

        try:
            from ceilometer.objectstore import rgw_client as c_rgw_client
            rgw_client = c_rgw_client.RGWAdminClient(endpoint,
                                                     self.access_key,
                                                     self.secret)
        except ImportError:
            raise plugin_base.PollsterPermanentError(tenants)

        for t in tenants:
            api_method = 'get_%s' % self.METHOD
            yield t.id, getattr(rgw_client, api_method)(t.id)


class ContainersObjectsPollster(_Base):
    """Get info about object counts in a container using RGW Admin APIs."""

    def get_samples(self, manager, cache, resources):
        for tenant, bucket_info in self._iter_accounts(manager.keystone,
                                                       cache, resources):
            for it in bucket_info['buckets']:
                yield sample.Sample(
                    name='radosgw.containers.objects',
                    type=sample.TYPE_GAUGE,
                    volume=int(it.num_objects),
                    unit='object',
                    user_id=None,
                    project_id=tenant,
                    resource_id=tenant + '/' + it.name,
                    resource_metadata=None,
                )


class ContainersSizePollster(_Base):
    """Get info about object sizes in a container using RGW Admin APIs."""

    def get_samples(self, manager, cache, resources):
        for tenant, bucket_info in self._iter_accounts(manager.keystone,
                                                       cache, resources):
            for it in bucket_info['buckets']:
                    yield sample.Sample(
                        name='radosgw.containers.objects.size',
                        type=sample.TYPE_GAUGE,
                        volume=int(it.size * 1024),
                        unit='B',
                        user_id=None,
                        project_id=tenant,
                        resource_id=tenant + '/' + it.name,
                        resource_metadata=None,
                    )


class ObjectsSizePollster(_Base):
    """Iterate over all accounts, using keystone."""

    def get_samples(self, manager, cache, resources):
        for tenant, bucket_info in self._iter_accounts(manager.keystone,
                                                       cache, resources):
            yield sample.Sample(
                name='radosgw.objects.size',
                type=sample.TYPE_GAUGE,
                volume=int(bucket_info['size'] * 1024),
                unit='B',
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                resource_metadata=None,
                )


class ObjectsPollster(_Base):
    """Iterate over all accounts, using keystone."""

    def get_samples(self, manager, cache, resources):
        for tenant, bucket_info in self._iter_accounts(manager.keystone,
                                                       cache, resources):
            yield sample.Sample(
                name='radosgw.objects',
                type=sample.TYPE_GAUGE,
                volume=int(bucket_info['num_objects']),
                unit='object',
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                resource_metadata=None,
                )


class ObjectsContainersPollster(_Base):
    def get_samples(self, manager, cache, resources):
        for tenant, bucket_info in self._iter_accounts(manager.keystone,
                                                       cache, resources):
            yield sample.Sample(
                name='radosgw.objects.containers',
                type=sample.TYPE_GAUGE,
                volume=int(bucket_info['num_buckets']),
                unit='object',
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                resource_metadata=None,
                )


class UsagePollster(_Base):

    METHOD = 'usage'

    def get_samples(self, manager, cache, resources):
        for tenant, usage in self._iter_accounts(manager.keystone,
                                                 cache, resources):
            yield sample.Sample(
                name='radosgw.api.request',
                type=sample.TYPE_GAUGE,
                volume=int(usage),
                unit='request',
                user_id=None,
                project_id=tenant,
                resource_id=tenant,
                resource_metadata=None,
                )
