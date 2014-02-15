# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance
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
import six.moves.urllib.parse as urlparse

import mock
import requests

from ceilometer.alarm import service
from ceilometer.openstack.common import context
from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common import test


DATA_JSON = ('{"current": "ALARM", "alarm_id": "foobar",'
             ' "reason": "what ?", "reason_data": {"test": "test"},'
             ' "previous": "OK"}')
NOTIFICATION = dict(alarm_id='foobar',
                    condition=dict(threshold=42),
                    reason='what ?',
                    reason_data={'test': 'test'},
                    previous='OK',
                    current='ALARM')


class TestAlarmNotifier(test.BaseTestCase):

    def setUp(self):
        super(TestAlarmNotifier, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        self.service = service.AlarmNotifierService('somehost', 'sometopic')

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_init_host(self):
        # If we try to create a real RPC connection, init_host() never
        # returns. Mock it out so we can establish the service
        # configuration.
        with mock.patch('ceilometer.openstack.common.rpc.create_connection'):
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
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0], (
            urlparse.urlsplit(data['actions'][0]),
            data['alarm_id'],
            data['previous'],
            data['current'],
            data['reason'],
            data['reason_data']))

    def test_notify_alarm_no_action(self):
        self.service.notify_alarm(context.get_admin_context(), {})

    def test_notify_alarm_log_action(self):
        self.service.notify_alarm(context.get_admin_context(),
                                  {
                                      'actions': ['log://'],
                                      'alarm_id': 'foobar',
                                      'condition': {'threshold': 42},
                                  })

    @staticmethod
    def _fake_spawn_n(func, *args, **kwargs):
        func(*args, **kwargs)

    @staticmethod
    def _notification(action):
        notification = {}
        notification.update(NOTIFICATION)
        notification['actions'] = [action]
        return notification

    def test_notify_alarm_rest_action_ok(self):
        action = 'http://host/action'

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                poster.assert_called_with(action, data=DATA_JSON)

    def test_notify_alarm_rest_action_with_ssl_client_cert(self):
        action = 'https://host/action'
        certificate = "/etc/ssl/cert/whatever.pem"

        self.CONF.set_override("rest_notifier_certificate_file", certificate,
                               group='alarm')

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                poster.assert_called_with(action, data=DATA_JSON,
                                          cert=certificate, verify=True)

    def test_notify_alarm_rest_action_with_ssl_client_cert_and_key(self):
        action = 'https://host/action'
        certificate = "/etc/ssl/cert/whatever.pem"
        key = "/etc/ssl/cert/whatever.key"

        self.CONF.set_override("rest_notifier_certificate_file", certificate,
                               group='alarm')
        self.CONF.set_override("rest_notifier_certificate_key", key,
                               group='alarm')

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                poster.assert_called_with(action, data=DATA_JSON,
                                          cert=(certificate, key), verify=True)

    def test_notify_alarm_rest_action_with_ssl_verify_disable_by_cfg(self):
        action = 'https://host/action'

        self.CONF.set_override("rest_notifier_ssl_verify", False,
                               group='alarm')

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                poster.assert_called_with(action, data=DATA_JSON,
                                          verify=False)

    def test_notify_alarm_rest_action_with_ssl_verify_disable(self):
        action = 'https://host/action?ceilometer-alarm-ssl-verify=0'

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                poster.assert_called_with(action, data=DATA_JSON,
                                          verify=False)

    def test_notify_alarm_rest_action_with_ssl_verify_enable_by_user(self):
        action = 'https://host/action?ceilometer-alarm-ssl-verify=1'

        self.CONF.set_override("rest_notifier_ssl_verify", False,
                               group='alarm')

        with mock.patch('eventlet.spawn_n', self._fake_spawn_n):
            with mock.patch.object(requests, 'post') as poster:
                self.service.notify_alarm(context.get_admin_context(),
                                          self._notification(action))
                poster.assert_called_with(action, data=DATA_JSON,
                                          verify=True)

    @staticmethod
    def _fake_urlsplit(*args, **kwargs):
        raise Exception("Evil urlsplit!")

    def test_notify_alarm_invalid_url(self):
        with mock.patch('ceilometer.openstack.common.network_utils.urlsplit',
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
