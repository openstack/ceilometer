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

from ceilometer import cache_utils
from ceilometer import service as ceilometer_service
from oslo_cache.backends import dictionary
from oslo_cache import core as cache
from oslo_config import fixture as config_fixture
from oslotest import base


class CacheConfFixture(config_fixture.Config):
    def setUp(self):
        super(CacheConfFixture, self).setUp()
        self.conf = ceilometer_service.\
            prepare_service(argv=[], config_files=[])
        cache.configure(self.conf)


class TestOsloCache(base.BaseTestCase):
    def setUp(self):
        super(TestOsloCache, self).setUp()

        conf = ceilometer_service.prepare_service(argv=[], config_files=[])

        dict_conf_fixture = CacheConfFixture(conf)
        self.useFixture(dict_conf_fixture)
        dict_conf_fixture.config(enabled=True, group='cache')
        dict_conf_fixture.config(expiration_time=600,
                                 backend='oslo_cache.dict',
                                 group='cache')
        self.dict_conf = dict_conf_fixture.conf

        # enable_retry_client is only supported by
        # 'dogpile.cache.pymemcache' backend which makes this
        # incorrect config
        faulty_conf_fixture = CacheConfFixture(conf)
        self.useFixture(faulty_conf_fixture)
        faulty_conf_fixture.config(enabled=True, group='cache')
        faulty_conf_fixture.config(expiration_time=600,
                                   backend='dogpile.cache.memcached',
                                   group='cache',
                                   enable_retry_client='true')
        self.faulty_conf = faulty_conf_fixture.conf

        no_cache_fixture = CacheConfFixture(conf)
        self.useFixture(no_cache_fixture)
        # no_cache_fixture.config()
        self.no_cache_conf = no_cache_fixture.conf

    def test_get_cache_region(self):
        self.assertIsNotNone(cache_utils.get_cache_region(self.dict_conf))

        # having invalid configurations will return None
        with self.assertLogs('ceilometer.cache_utils', level='ERROR') as logs:
            self.assertIsNone(
                cache_utils.get_cache_region(self.faulty_conf)
            )
            cache_configure_failed = logs.output
            self.assertIn(
                'ERROR:ceilometer.cache_utils:'
                'failed to configure oslo_cache: '
                'Retry client is only supported by '
                'the \'dogpile.cache.pymemcache\' backend.',
                cache_configure_failed)

    def test_get_client(self):
        dict_cache_client = cache_utils.get_client(self.dict_conf)
        self.assertIsNotNone(dict_cache_client)
        self.assertIsInstance(dict_cache_client.region.backend,
                              dictionary.DictCacheBackend)

        no_cache_config = cache_utils.get_client(self.no_cache_conf)
        self.assertIsNotNone(no_cache_config)
        self.assertIsInstance(dict_cache_client.region.backend,
                              dictionary.DictCacheBackend)

        # having invalid configurations will return None
        with self.assertLogs('ceilometer.cache_utils', level='ERROR') as logs:
            cache_client = cache_utils.get_client(self.faulty_conf)
            cache_configure_failed = logs.output
            self.assertIsNone(cache_client)
            self.assertIn(
                'ERROR:ceilometer.cache_utils:'
                'failed to configure oslo_cache: '
                'Retry client is only supported by '
                'the \'dogpile.cache.pymemcache\' backend.',
                cache_configure_failed)
