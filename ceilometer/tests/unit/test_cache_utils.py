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
from oslo_cache import core as cache
from oslo_config import fixture as config_fixture
from oslotest import base


class CacheConfFixture(config_fixture.Config):
    def setUp(self):
        super(CacheConfFixture, self).setUp()
        self.conf = ceilometer_service.\
            prepare_service(argv=[], config_files=[])
        cache.configure(self.conf)
        self.config(enabled=True, group='cache')


class TestOsloCache(base.BaseTestCase):
    def setUp(self):
        super(TestOsloCache, self).setUp()

        conf = ceilometer_service.prepare_service(argv=[], config_files=[])

        dict_conf_fixture = CacheConfFixture(conf)
        self.useFixture(dict_conf_fixture)
        dict_conf_fixture.config(expiration_time=600,
                                 backend='oslo_cache.dict',
                                 group='cache')
        self.dict_conf = dict_conf_fixture.conf

        # enable_retry_client is only supported by
        # 'dogpile.cache.pymemcache' backend which makes this
        # incorrect config
        faulty_conf_fixture = CacheConfFixture(conf)
        self.useFixture(faulty_conf_fixture)
        faulty_conf_fixture.config(expiration_time=600,
                                   backend='dogpile.cache.memcached',
                                   group='cache',
                                   enable_retry_client='true')
        self.faulty_cache_conf = faulty_conf_fixture.conf

        self.no_cache_conf = ceilometer_service.\
            prepare_service(argv=[], config_files=[])

    def test_get_cache_region(self):
        self.assertIsNotNone(cache_utils.get_cache_region(self.dict_conf))

    def test_get_client(self):
        self.assertIsNotNone(cache_utils.get_client(self.dict_conf))
        self.assertIsNone(cache_utils.get_client(self.no_cache_conf))
        self.assertIsNone(cache_utils.get_client(self.faulty_cache_conf))
