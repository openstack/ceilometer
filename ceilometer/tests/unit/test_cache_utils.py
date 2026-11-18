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
from ceilometer.tests import base
from ceilometer.tests.unit import fakes
from openstack.identity.v3 import project as sdk_project
from openstack.identity.v3 import user as sdk_user
from oslo_cache.backends import dictionary
from oslo_cache import core as cache
from oslo_config import fixture as config_fixture


class CacheConfFixture(config_fixture.Config):
    def setUp(self):
        super().setUp()
        self.conf = ceilometer_service.\
            prepare_service(argv=[], config_files=[])
        cache.configure(self.conf)


class TestOsloCache(base.BaseTestCase):
    def setUp(self):
        super().setUp()

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


class TestResolveUuidFromKeystone(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        self.CONF = ceilometer_service.prepare_service([], [])
        self.setup_connection()
        self.cache_client = cache_utils.get_client(self.CONF)

    def test_resolve_project_name(self):
        self.assertEqual(
            fakes.PROJECT_ADMIN_ceilo.name,
            self.cache_client.resolve_uuid_from_cache(
                'projects', fakes.PROJECT_ADMIN_ceilo.id))

    def test_resolve_user_name(self):
        self.assertEqual(
            fakes.USER_ADMIN_ceilo.name,
            self.cache_client.resolve_uuid_from_cache(
                'users', fakes.USER_ADMIN_ceilo.id))

    def test_resolve_unknown_resource_type(self):
        with self.assertLogs('ceilometer.cache_utils', level='WARNING'):
            self.assertIsNone(
                self.cache_client._resolve_uuid_from_keystone(
                    'unknown', 'some-uuid'))

    def test_resolve_not_found(self):
        with self.assertLogs('ceilometer.cache_utils', level='WARNING'):
            self.assertIsNone(
                self.cache_client.resolve_uuid_from_cache(
                    'projects', 'nonexistent-project'))

    def test_resolved_name_is_cached(self):
        self.cache_client.resolve_uuid_from_cache(
            'projects', fakes.PROJECT_ADMIN_ceilo.id)
        self.cache_client.resolve_uuid_from_cache(
            'projects', fakes.PROJECT_ADMIN_ceilo.id)

        self.assertEqual(1, self.fake_conn.search_projects.call_count)

    def test_not_found_is_not_cached(self):
        self.cache_client.resolve_uuid_from_cache(
            'projects', 'nonexistent-project')
        self.cache_client.resolve_uuid_from_cache(
            'projects', 'nonexistent-project')

        self.assertEqual(2, self.fake_conn.search_projects.call_count)

    def test_keystone_client_is_reused(self):
        self.cache_client.resolve_uuid_from_cache(
            'projects', fakes.PROJECT_ADMIN_ceilo.id)
        self.cache_client.resolve_uuid_from_cache(
            'users', fakes.USER_ADMIN_ceilo.id)
        self.cache_client.resolve_uuid_from_cache(
            'projects', 'nonexistent-project')

        self.assertEqual(1, self.fake_conn_class_mock.call_count)

    def test_project_and_user_with_same_id(self):
        shared_id = 'shared-id'
        self.setup_connection(
            projects=[sdk_project.Project(
                connection=None, id=shared_id, name='a-project',
                parent_id='default', domain_id='default',
                is_domain=False, is_enabled=True)],
            users=[sdk_user.User(
                connection=None, id=shared_id, name='a-user',
                domain_id='default', is_enabled=True)])

        self.assertEqual(
            'a-project',
            self.cache_client.resolve_uuid_from_cache('projects', shared_id))
        self.assertEqual(
            'a-user',
            self.cache_client.resolve_uuid_from_cache('users', shared_id))
        # Both lookups must still be served from the cache afterwards
        self.assertEqual(
            'a-project',
            self.cache_client.resolve_uuid_from_cache('projects', shared_id))
        self.assertEqual(
            'a-user',
            self.cache_client.resolve_uuid_from_cache('users', shared_id))
        self.assertEqual(1, self.fake_conn.search_projects.call_count)
        self.assertEqual(1, self.fake_conn.search_users.call_count)
