# -*- encoding: utf-8 -*-
#
# Author: John Tran <jhtran@att.com>
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

import functools

import novaclient
from novaclient.v1_1 import client as nova_client
from oslo.config import cfg

from ceilometer.openstack.common import log

cfg.CONF.import_group('service_credentials', 'ceilometer.service')

LOG = log.getLogger(__name__)


def logged(func):

    @functools.wraps(func)
    def with_logging(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            LOG.exception(e)
            raise

    return with_logging


class Client(object):
    """A client which gets information via python-novaclient."""

    def __init__(self):
        """Initialize a nova client object."""
        conf = cfg.CONF.service_credentials
        tenant = conf.os_tenant_id or conf.os_tenant_name
        self.nova_client = nova_client.Client(
            username=conf.os_username,
            api_key=conf.os_password,
            project_id=tenant,
            auth_url=conf.os_auth_url,
            region_name=conf.os_region_name,
            endpoint_type=conf.os_endpoint_type,
            cacert=conf.os_cacert,
            no_cache=True)

    def _with_flavor_and_image(self, instances):
        for instance in instances:
            self._with_flavor(instance)
            self._with_image(instance)

        return instances

    def _with_flavor(self, instance):
        fid = instance.flavor['id']
        try:
            flavor = self.nova_client.flavors.get(fid)
        except novaclient.exceptions.NotFound:
            flavor = None

        attr_defaults = [('name', 'unknown-id-%s' % fid),
                         ('vcpus', 0), ('ram', 0), ('disk', 0),
                         ('ephemeral', 0)]

        for attr, default in attr_defaults:
            if not flavor:
                instance.flavor[attr] = default
                continue
            instance.flavor[attr] = getattr(flavor, attr, default)

    def _with_image(self, instance):
        try:
            iid = instance.image['id']
        except TypeError:
            instance.image = None
            instance.kernel_id = None
            instance.ramdisk_id = None
            return

        try:
            image = self.nova_client.images.get(iid)
        except novaclient.exceptions.NotFound:
            instance.image['name'] = 'unknown-id-%s' % iid
            instance.kernel_id = None
            instance.ramdisk_id = None
            return

        instance.image['name'] = getattr(image, 'name')
        image_metadata = getattr(image, 'metadata', None)

        for attr in ['kernel_id', 'ramdisk_id']:
            ameta = image_metadata.get(attr) if image_metadata else None
            setattr(instance, attr, ameta)

    @logged
    def instance_get_all_by_host(self, hostname):
        """Returns list of instances on particular host."""
        search_opts = {'host': hostname, 'all_tenants': True}
        return self._with_flavor_and_image(self.nova_client.servers.list(
            detailed=True,
            search_opts=search_opts))

    @logged
    def floating_ip_get_all(self):
        """Returns all floating ips."""
        return self.nova_client.floating_ips.list()
