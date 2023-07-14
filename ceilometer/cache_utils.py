#
# Copyright 2022 Red Hat, Inc
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

"""Simple wrapper for oslo_cache."""
import uuid

from ceilometer import keystone_client
from keystoneauth1 import exceptions as ka_exceptions
from oslo_cache import core as cache
from oslo_cache import exception
from oslo_log import log
from oslo_utils.secretutils import md5

# Default cache expiration period
CACHE_DURATION = 600

NAME_ENCODED = __name__.encode('utf-8')
CACHE_NAMESPACE = uuid.UUID(
    bytes=md5(NAME_ENCODED, usedforsecurity=False).digest()
)

LOG = log.getLogger(__name__)


class CacheClient(object):
    def __init__(self, region, conf):
        self.region = region
        self.conf = conf

    def get(self, key):
        value = self.region.get(key)
        if value == cache.NO_VALUE:
            return None
        return value

    def set(self, key, value):
        return self.region.set(key, value)

    def delete(self, key):
        return self.region.delete(key)

    def resolve_uuid_from_cache(self, attr, uuid):
        resource_name = self.get(uuid)
        if resource_name:
            return resource_name
        else:
            # Retrieve project and user names from Keystone only
            # if ceilometer doesn't have a caching backend
            resource_name = self._resolve_uuid_from_keystone(attr, uuid)
            self.set(uuid, resource_name)
            return resource_name

    def _resolve_uuid_from_keystone(self, attr, uuid):
        try:
            return getattr(
                keystone_client.get_client(self.conf), attr
            ).get(uuid).name
        except AttributeError as e:
            LOG.warning("Found '%s' while resolving uuid %s to name", e, uuid)
        except ka_exceptions.NotFound as e:
            LOG.warning(e.message)


def get_client(conf):
    cache.configure(conf)
    if conf.cache.enabled:
        region = get_cache_region(conf)
        if region:
            return CacheClient(region, conf)
    else:
        # configure oslo_cache.dict backend if
        # no caching backend is configured
        region = get_dict_cache_region()
        return CacheClient(region, conf)


def get_dict_cache_region():
    region = cache.create_region()
    region.configure('oslo_cache.dict', expiration_time=CACHE_DURATION)
    return region


def get_cache_region(conf):
    # configure caching region using params from config
    try:
        region = cache.create_region()
        cache.configure_cache_region(conf, region)
        return region

    except exception.ConfigurationError as e:
        LOG.error("failed to configure oslo_cache: %s", str(e))


def cache_key_mangler(key):
    """Construct an opaque cache key."""

    return uuid.uuid5(CACHE_NAMESPACE, key).hex
