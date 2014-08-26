#
# Copyright 2013-2014 eNovance
#
# Author: Julien Danjou <julien@danjou.info>
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

import anyjson
import mock
from oslo.config import fixture as fixture_config
from oslotest import mockpatch
import requests
import six.moves.urllib.parse as urlparse

from ceilometer.alarm import service
from ceilometer.openstack.common import context
from ceilometer.tests import base as tests_base


DATA_JSON = anyjson.loads(
    '{"current": "ALARM", "alarm_id": "foobar",'
    ' "reason": "what ?", "reason_data": {"test": "test"},'
    ' "previous": "OK"}'
)
NOTIFICATION = dict(alarm_id='foobar',
                    condition=dict(threshold=42),
                    reason='what ?',
                    reason_data={'test': 'test'},
                    previous='OK',
                    current='ALARM')


class TestAlarmNotifier(tests_base.BaseTestCase):

    def setUp(self):
        super(TestAlarmNotifier, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.setup_messaging(self.CONF)
        self.service = service.AlarmNotifierService()
        self.useFixture(mockpatch.Patch(
            'ceilometer.openstack.common.context.generate_request_id',
            self._fake_generate_request_id))

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_init_host(self):
        # If we try to create a real RPC connection, init_host() never
        # returns. Mock it out so we can establish the service
        # configuration.
        with mock.patch.object(self.service.rpc_server, 'start'):
            self.service.start()

    def test_notify_alarm(self):
        data = {
            'actions': ['test://'],
            'alarm_id': 'foobar',
            'previous': 'OK',
            'current': 'ALARM',
            'reason': 'Everything is on fire',
            'reason_data': {'fire': 'everywhere'}
        }
        self.service.notify_alarm(context.get_admin_context(), data)
        notifications = self.service.notifiers['test'].obj.notifications
        self.assertEqual(1, len(notifications))
        self.assertEqual((urlparse.urlsplit(data['actions'][0]),
                          data['alarm_id'],
                          data['previous'],
                          data['current'],
                          data['reason'],
                          data['reason_data']),
                         notifications[0])

    def test_notify_alarm_no_action(self):
        self.service.notify_alarm(context.get_admin_context(), {})

    def test_notify_alarm_log_action(self):
        self.service.notify_alarm(context.get_admin_context(),
                                  {
                                      'actions': ['log://'],
                                      'alarm_id': 'foobar',
                                      'condition': {'threshold': 42}})

    @staticmethod
    def _fake_spawn_n(func, *args, **kwargs):
        func(*args, **kwargs)

    @staticmethod
    def _notification(action):
        notification = {}
        notification.update(NOTIFICATION)
        notification['actions'] = [action]
        return notification

    HTTP_HEADERS = {'x-openstack-request-id': 'fake_request_id',
                    'content-type': 'application/json'}

    def _fake_generate_request_id(self):
        return self.HTTP_HEADERS['x-openstack-request-id']

    def test_notify_alarm_rest_action_ok(self):
        action = 'http://host/action'

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests.Session, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                poster.assert_called_with(action, data=mock.ANY,
                                          headers=mock.ANY)
                args, kwargs = poster.call_args
                self.assertEqual(self.HTTP_HEADERS, kwargs['headers'])
                self.assertEqual(DATA_JSON, anyjson.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_client_cert(self):
        action = 'https://host/action'
        certificate = "/etc/ssl/cert/whatever.pem"

        self.CONF.set_override("rest_notifier_certificate_file", certificate,
                               group='alarm')

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests.Session, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                poster.assert_called_with(action, data=mock.ANY,
                                          headers=mock.ANY,
                                          cert=certificate, verify=True)
                args, kwargs = poster.call_args
                self.assertEqual(self.HTTP_HEADERS, kwargs['headers'])
                self.assertEqual(DATA_JSON, anyjson.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_client_cert_and_key(self):
        action = 'https://host/action'
        certificate = "/etc/ssl/cert/whatever.pem"
        key = "/etc/ssl/cert/whatever.key"

        self.CONF.set_override("rest_notifier_certificate_file", certificate,
                               group='alarm')
        self.CONF.set_override("rest_notifier_certificate_key", key,
                               group='alarm')

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests.Session, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                poster.assert_called_with(action, data=mock.ANY,
                                          headers=mock.ANY,
                                          cert=(certificate, key), verify=True)
                args, kwargs = poster.call_args
                self.assertEqual(self.HTTP_HEADERS, kwargs['headers'])
                self.assertEqual(DATA_JSON, anyjson.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_verify_disable_by_cfg(self):
        action = 'https://host/action'

        self.CONF.set_override("rest_notifier_ssl_verify", False,
                               group='alarm')

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests.Session, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                poster.assert_called_with(action, data=mock.ANY,
                                          headers=mock.ANY,
                                          verify=False)
                args, kwargs = poster.call_args
                self.assertEqual(self.HTTP_HEADERS, kwargs['headers'])
                self.assertEqual(DATA_JSON, anyjson.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_verify_disable(self):
        action = 'https://host/action?ceilometer-alarm-ssl-verify=0'

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests.Session, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                poster.assert_called_with(action, data=mock.ANY,
                                          headers=mock.ANY,
                                          verify=False)
                args, kwargs = poster.call_args
                self.assertEqual(self.HTTP_HEADERS, kwargs['headers'])
                self.assertEqual(DATA_JSON, anyjson.loads(kwargs['data']))

    def test_notify_alarm_rest_action_with_ssl_verify_enable_by_user(self):
        action = 'https://host/action?ceilometer-alarm-ssl-verify=1'

        self.CONF.set_override("rest_notifier_ssl_verify", False,
                               group='alarm')

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests.Session, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                poster.assert_called_with(action, data=mock.ANY,
                                          headers=mock.ANY,
                                          verify=True)
                args, kwargs = poster.call_args
                self.assertEqual(self.HTTP_HEADERS, kwargs['headers'])
                self.assertEqual(DATA_JSON, anyjson.loads(kwargs['data']))

    @staticmethod
    def _fake_urlsplit(*args, **kwargs):
        raise Exception("Evil urlsplit!")

    def test_notify_alarm_invalid_url(self):
        with mock.patch('oslo.utils.netutils.urlsplit',
                        self._fake_urlsplit):
            LOG = mock.MagicMock()
            with mock.patch('ceilometer.alarm.service.LOG', LOG):
                self.service.notify_alarm(
                    context.get_admin_context(),
                    {
                        'actions': ['no-such-action-i-am-sure'],
                        'alarm_id': 'foobar',
                        'condition': {'threshold': 42},
                    })
                self.assertTrue(LOG.error.called)

    def test_notify_alarm_invalid_action(self):
        LOG = mock.MagicMock()
        with mock.patch('ceilometer.alarm.service.LOG', LOG):
            self.service.notify_alarm(
                context.get_admin_context(),
                {
                    'actions': ['no-such-action-i-am-sure://'],
                    'alarm_id': 'foobar',
                    'condition': {'threshold': 42},
                })
            self.assertTrue(LOG.error.called)

    def test_notify_alarm_trust_action(self):
        action = 'trust+http://trust-1234@host/action'
        url = 'http://host/action'

        client = mock.MagicMock()
        client.auth_token = 'token_1234'
        headers = {'X-Auth-Token': 'token_1234'}
        headers.update(self.HTTP_HEADERS)

        self.useFixture(mockpatch.Patch('keystoneclient.v3.client.Client',
                                        lambda **kwargs: client))

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests.Session, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                headers = {'X-Auth-Token': 'token_1234'}
                headers.update(self.HTTP_HEADERS)
                poster.assert_called_with(
                    url, data=mock.ANY, headers=mock.ANY)
                args, kwargs = poster.call_args
                self.assertEqual(headers, kwargs['headers'])
                self.assertEqual(DATA_JSON, anyjson.loads(kwargs['data']))
