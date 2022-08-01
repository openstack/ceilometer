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


from oslo_cache import core as cache


class CacheClient(object):
    def __init__(self, region):
        self.region = region

    def get(self, key):
        value = self.region.get(key)
        if value == cache.NO_VALUE:
            return None
        return value

    def set(self, key, value):
        return self.region.set(key, value)

    def delete(self, key):
        return self.region.delete(key)


def get_client(conf, expiration_time=0):
    cache.configure(conf)
    if conf.cache.enabled:
        return CacheClient(_get_default_cache_region(
            conf,
            expiration_time=expiration_time
        ))


def _get_default_cache_region(conf, expiration_time):
    region = cache.create_region()
    if expiration_time != 0:
        conf.cache.expiration_time = expiration_time
    cache.configure_cache_region(conf, region)
    return region
