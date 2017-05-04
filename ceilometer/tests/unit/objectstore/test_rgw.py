# Copyright 2015 Reliance Jio Infocomm Ltd
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

import collections

import fixtures
from keystoneauth1 import exceptions
import mock
from oslotest import base
import testscenarios.testcase

from ceilometer.agent import manager
from ceilometer.objectstore import rgw
from ceilometer.objectstore import rgw_client
from ceilometer import service

bucket_list1 = [rgw_client.RGWAdminClient.Bucket('somefoo1', 10, 7)]
bucket_list2 = [rgw_client.RGWAdminClient.Bucket('somefoo2', 2, 9)]
bucket_list3 = [rgw_client.RGWAdminClient.Bucket('unlisted', 100, 100)]

GET_BUCKETS = [('tenant-000', {'num_buckets': 2, 'size': 1042,
                               'num_objects': 1001, 'buckets': bucket_list1}),
               ('tenant-001', {'num_buckets': 2, 'size': 1042,
                               'num_objects': 1001, 'buckets': bucket_list2}),
               ('tenant-002-ignored', {'num_buckets': 2, 'size': 1042,
                                       'num_objects': 1001,
                                       'buckets': bucket_list3})]

GET_USAGE = [('tenant-000', 10),
             ('tenant-001', 11),
             ('tenant-002-ignored', 12)]

Tenant = collections.namedtuple('Tenant', 'id')
ASSIGNED_TENANTS = [Tenant('tenant-000'), Tenant('tenant-001')]


class TestManager(manager.AgentManager):

    def __init__(self, worker_id, conf):
        super(TestManager, self).__init__(worker_id, conf)
        self._keystone = mock.Mock()
        self._catalog = (self._keystone.session.auth.get_access.
                         return_value.service_catalog)
        self._catalog.url_for.return_value = 'http://foobar/endpoint'


class TestRgwPollster(testscenarios.testcase.WithScenarios,
                      base.BaseTestCase):

    # Define scenarios to run all of the tests against all of the
    # pollsters.
    scenarios = [
        ('radosgw.objects',
         {'factory': rgw.ObjectsPollster}),
        ('radosgw.objects.size',
         {'factory': rgw.ObjectsSizePollster}),
        ('radosgw.objects.containers',
         {'factory': rgw.ObjectsContainersPollster}),
        ('radosgw.containers.objects',
         {'factory': rgw.ContainersObjectsPollster}),
        ('radosgw.containers.objects.size',
         {'factory': rgw.ContainersSizePollster}),
        ('radosgw.api.request',
         {'factory': rgw.UsagePollster}),
    ]

    @staticmethod
    def fake_ks_service_catalog_url_for(*args, **kwargs):
        raise exceptions.EndpointNotFound("Fake keystone exception")

    def fake_iter_accounts(self, ksclient, cache, tenants):
        tenant_ids = [t.id for t in tenants]
        for i in self.ACCOUNTS:
            if i[0] in tenant_ids:
                yield i

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestRgwPollster, self).setUp()
        conf = service.prepare_service([], [])
        conf.set_override('radosgw', 'object-store',
                          group='service_types')
        self.pollster = self.factory(conf)
        self.manager = TestManager(0, conf)

        if self.pollster.CACHE_KEY_METHOD == 'rgw.get_bucket':
            self.ACCOUNTS = GET_BUCKETS
        else:
            self.ACCOUNTS = GET_USAGE

    def tearDown(self):
        super(TestRgwPollster, self).tearDown()
        rgw._Base._ENDPOINT = None

    def test_iter_accounts_no_cache(self):
        cache = {}
        with fixtures.MockPatchObject(self.factory, '_get_account_info',
                                      return_value=[]):
            data = list(self.pollster._iter_accounts(mock.Mock(), cache,
                                                     ASSIGNED_TENANTS))

        self.assertIn(self.pollster.CACHE_KEY_METHOD, cache)
        self.assertEqual([], data)

    def test_iter_accounts_cached(self):
        # Verify that if a method has already been called, _iter_accounts
        # uses the cached version and doesn't call rgw_clinet.
        mock_method = mock.Mock()
        mock_method.side_effect = AssertionError(
            'should not be called',
        )

        api_method = 'get_%s' % self.pollster.METHOD

        with fixtures.MockPatchObject(rgw_client.RGWAdminClient,
                                      api_method, new=mock_method):
            cache = {self.pollster.CACHE_KEY_METHOD: [self.ACCOUNTS[0]]}
            data = list(self.pollster._iter_accounts(mock.Mock(), cache,
                                                     ASSIGNED_TENANTS))
        self.assertEqual([self.ACCOUNTS[0]], data)

    def test_metering(self):
        with fixtures.MockPatchObject(self.factory, '_iter_accounts',
                                      side_effect=self.fake_iter_accounts):
            samples = list(self.pollster.get_samples(self.manager, {},
                                                     ASSIGNED_TENANTS))

        self.assertEqual(2, len(samples), self.pollster.__class__)

    def test_get_meter_names(self):
        with fixtures.MockPatchObject(self.factory, '_iter_accounts',
                                      side_effect=self.fake_iter_accounts):
            samples = list(self.pollster.get_samples(self.manager, {},
                                                     ASSIGNED_TENANTS))

        self.assertEqual(set([samples[0].name]),
                         set([s.name for s in samples]))

    def test_only_poll_assigned(self):
        mock_method = mock.MagicMock()
        endpoint = 'http://127.0.0.1:8000/admin'
        api_method = 'get_%s' % self.pollster.METHOD
        with fixtures.MockPatchObject(rgw_client.RGWAdminClient,
                                      api_method, new=mock_method):
            with fixtures.MockPatchObject(
                    self.manager._catalog, 'url_for',
                    return_value=endpoint):
                list(self.pollster.get_samples(self.manager, {},
                                               ASSIGNED_TENANTS))
        expected = [mock.call(t.id)
                    for t in ASSIGNED_TENANTS]
        self.assertEqual(expected, mock_method.call_args_list)

    def test_get_endpoint_only_once(self):
        mock_url_for = mock.MagicMock()
        mock_url_for.return_value = '/endpoint'
        api_method = 'get_%s' % self.pollster.METHOD
        with fixtures.MockPatchObject(rgw_client.RGWAdminClient, api_method,
                                      new=mock.MagicMock()):
            with fixtures.MockPatchObject(
                    self.manager._catalog, 'url_for',
                    new=mock_url_for):
                list(self.pollster.get_samples(self.manager, {},
                                               ASSIGNED_TENANTS))
                list(self.pollster.get_samples(self.manager, {},
                                               ASSIGNED_TENANTS))
        self.assertEqual(1, mock_url_for.call_count)

    def test_endpoint_notfound(self):
        with fixtures.MockPatchObject(
                self.manager._catalog, 'url_for',
                side_effect=self.fake_ks_service_catalog_url_for):
            samples = list(self.pollster.get_samples(self.manager, {},
                                                     ASSIGNED_TENANTS))

        self.assertEqual(0, len(samples))
