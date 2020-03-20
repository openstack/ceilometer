# Copyright 2015 Hewlett-Packard Company
# (c) Copyright 2018 SUSE LLC
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
from unittest import mock

from monascaclient import exc
from oslo_utils import netutils
from oslotest import base
import tenacity

from ceilometer import monasca_client
from ceilometer import service


class TestMonascaClient(base.BaseTestCase):
    def setUp(self):
        super(TestMonascaClient, self).setUp()

        self.CONF = service.prepare_service([], [])
        self.CONF.set_override('client_max_retries', 0, 'monasca')
        self.mc = self._get_client()

    def tearDown(self):
        # For some reason, cfg.CONF is registered a required option named
        # auth_url after these tests run, which occasionally blocks test
        # case test_event_pipeline_endpoint_requeue_on_failure, so we
        # unregister it here.
        self.CONF.reset()
        # self.CONF.unregister_opt(cfg.StrOpt('service_auth_url'),
        #                          group='monasca')
        super(TestMonascaClient, self).tearDown()

    @mock.patch('monascaclient.client.Client')
    def _get_client(self, monclient_mock):
        return monasca_client.Client(
            self.CONF,
            netutils.urlsplit("http://127.0.0.1:8080"))

    @mock.patch('monascaclient.client.Client')
    def test_client_url_correctness(self, monclient_mock):
        mon_client = monasca_client.Client(
            self.CONF,
            netutils.urlsplit("monasca://https://127.0.0.1:8080"))
        self.assertEqual("https://127.0.0.1:8080", mon_client._endpoint)

    def test_metrics_create(self):
        with mock.patch.object(self.mc._mon_client.metrics, 'create',
                               side_effect=[True]) as create_patch:
            self.mc.metrics_create()

            self.assertEqual(1, create_patch.call_count)

    def test_metrics_create_exception(self):
        with mock.patch.object(
                self.mc._mon_client.metrics, 'create',
                side_effect=[exc.http.InternalServerError, True])\
                as create_patch:
            e = self.assertRaises(tenacity.RetryError,
                                  self.mc.metrics_create)
            original_ex = e.last_attempt.exception()
            self.assertIsInstance(original_ex,
                                  monasca_client.MonascaServiceException)
            self.assertEqual(1, create_patch.call_count)

    def test_metrics_create_unprocessable_exception(self):
        with mock.patch.object(
                self.mc._mon_client.metrics, 'create',
                side_effect=[exc.http.UnprocessableEntity, True])\
                as create_patch:
            self.assertRaises(monasca_client.MonascaInvalidParametersException,
                              self.mc.metrics_create)
            self.assertEqual(1, create_patch.call_count)

    def test_no_retry_on_invalid_parameter(self):
        self.CONF.set_override('client_max_retries', 2, 'monasca')
        self.CONF.set_override('client_retry_interval', 1, 'monasca')
        self.mc = self._get_client()

        def _check(exception):
            expected_exc = monasca_client.MonascaInvalidParametersException
            with mock.patch.object(
                    self.mc._mon_client.metrics, 'create',
                    side_effect=[exception, True]
            ) as mocked_metrics_list:
                self.assertRaises(expected_exc, self.mc.metrics_create)
                self.assertEqual(1, mocked_metrics_list.call_count)

        _check(exc.http.UnprocessableEntity)
        _check(exc.http.BadRequest)

    def test_max_retries_not_too_much(self):
        def _check(configured, expected):
            self.CONF.set_override('client_max_retries', configured,
                                   'monasca')
            self.mc = self._get_client()
            self.assertEqual(expected, self.mc._max_retries)

        _check(-1, 10)
        _check(11, 10)
        _check(5, 5)
        _check(None, 1)

    def test_meaningful_exception_message(self):
        with mock.patch.object(
                self.mc._mon_client.metrics, 'create',
                side_effect=[exc.http.InternalServerError,
                             exc.http.UnprocessableEntity,
                             KeyError]):
            e = self.assertRaises(
                tenacity.RetryError,
                self.mc.metrics_create)
            original_ex = e.last_attempt.exception()
            self.assertIn('Monasca service is unavailable',
                          str(original_ex))

            e = self.assertRaises(
                monasca_client.MonascaInvalidParametersException,
                self.mc.metrics_create)
            self.assertIn('Request cannot be handled by Monasca',
                          str(e))

            e = self.assertRaises(
                tenacity.RetryError,
                self.mc.metrics_create)
            original_ex = e.last_attempt.exception()
            self.assertIn('An exception is raised from Monasca',
                          str(original_ex))

    @mock.patch.object(monasca_client.Client, '_get_client')
    def test_metrics_create_with_401(self, rc_patch):
        with mock.patch.object(
                self.mc._mon_client.metrics, 'create',
                side_effect=[exc.http.Unauthorized, True]):
            self.assertRaises(
                monasca_client.MonascaInvalidParametersException,
                self.mc.metrics_create)
