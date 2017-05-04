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

import fixtures
import mock
from oslo_utils import fileutils
import six

from ceilometer.tests.functional.api import v2


class TestAPIUpgradePath(v2.FunctionalTest):
    def _make_app(self):
        content = ('{"default": ""}')
        if six.PY3:
            content = content.encode('utf-8')
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='policy',
                                                    suffix='.json')
        self.CONF.set_override("policy_file", self.tempfile,
                               group='oslo_policy')
        return super(TestAPIUpgradePath, self)._make_app()

    def _setup_osloconfig_options(self):
        self.CONF.set_override('gnocchi_is_enabled', True, group='api')
        self.CONF.set_override('aodh_is_enabled', True, group='api')
        self.CONF.set_override('aodh_url', 'http://alarm-endpoint:8008/',
                               group='api')
        self.CONF.set_override('panko_is_enabled', True, group='api')
        self.CONF.set_override('panko_url', 'http://event-endpoint:8009/',
                               group='api')

    def _setup_keystone_mock(self):
        self.CONF.set_override('gnocchi_is_enabled', None, group='api')
        self.CONF.set_override('aodh_is_enabled', None, group='api')
        self.CONF.set_override('aodh_url', None, group='api')
        self.CONF.set_override('panko_is_enabled', None, group='api')
        self.CONF.set_override('panko_url', None, group='api')
        self.CONF.set_override('meter_dispatchers', ['database'])
        self.ks = mock.Mock()
        self.catalog = (self.ks.session.auth.get_access.
                        return_value.service_catalog)
        self.catalog.url_for.side_effect = self._url_for
        self.useFixture(fixtures.MockPatch(
            'ceilometer.keystone_client.get_client', return_value=self.ks))

    @staticmethod
    def _url_for(service_type=None):
        if service_type == 'metric':
            return 'http://gnocchi/'
        elif service_type == 'alarming':
            return 'http://alarm-endpoint:8008/'
        elif service_type == 'event':
            return 'http://event-endpoint:8009/'

    def _do_test_gnocchi_enabled_without_database_backend(self):
        self.CONF.set_override('meter_dispatchers', ['gnocchi'])
        for endpoint in ['meters', 'samples', 'resources']:
            response = self.app.get(self.PATH_PREFIX + '/' + endpoint,
                                    status=410)
            self.assertIn(b'Gnocchi API', response.body)

        response = self.post_json('/query/samples',
                                  params={
                                      "filter": '{"=": {"type": "creation"}}',
                                      "orderby": '[{"timestamp": "DESC"}]',
                                      "limit": 3
                                  }, status=410)
        self.assertIn(b'Gnocchi API', response.body)
        sample_params = {
            "counter_type": "gauge",
            "counter_name": "fake_counter",
            "resource_id": "fake_resource_id",
            "counter_unit": "fake_unit",
            "counter_volume": "1"
        }
        self.post_json('/meters/fake_counter',
                       params=[sample_params],
                       status=201)
        response = self.post_json('/meters/fake_counter?direct=1',
                                  params=[sample_params],
                                  status=400)
        self.assertIn(b'direct option cannot be true when Gnocchi is enabled',
                      response.body)

    def _do_test_alarm_redirect(self):
        response = self.app.get(self.PATH_PREFIX + '/alarms',
                                expect_errors=True)

        self.assertEqual(308, response.status_code)
        self.assertEqual("http://alarm-endpoint:8008/v2/alarms",
                         response.headers['Location'])

        response = self.app.get(self.PATH_PREFIX + '/alarms/uuid',
                                expect_errors=True)

        self.assertEqual(308, response.status_code)
        self.assertEqual("http://alarm-endpoint:8008/v2/alarms/uuid",
                         response.headers['Location'])

        response = self.app.delete(self.PATH_PREFIX + '/alarms/uuid',
                                   expect_errors=True)

        self.assertEqual(308, response.status_code)
        self.assertEqual("http://alarm-endpoint:8008/v2/alarms/uuid",
                         response.headers['Location'])

        response = self.post_json('/query/alarms',
                                  params={
                                      "filter": '{"=": {"type": "creation"}}',
                                      "orderby": '[{"timestamp": "DESC"}]',
                                      "limit": 3
                                  }, status=308)
        self.assertEqual("http://alarm-endpoint:8008/v2/query/alarms",
                         response.headers['Location'])

    def _do_test_event_redirect(self):
        response = self.app.get(self.PATH_PREFIX + '/events',
                                expect_errors=True)

        self.assertEqual(308, response.status_code)
        self.assertEqual("http://event-endpoint:8009/v2/events",
                         response.headers['Location'])

        response = self.app.get(self.PATH_PREFIX + '/events/uuid',
                                expect_errors=True)

        self.assertEqual(308, response.status_code)
        self.assertEqual("http://event-endpoint:8009/v2/events/uuid",
                         response.headers['Location'])

        response = self.app.delete(self.PATH_PREFIX + '/events/uuid',
                                   expect_errors=True)

        self.assertEqual(308, response.status_code)
        self.assertEqual("http://event-endpoint:8009/v2/events/uuid",
                         response.headers['Location'])

        response = self.app.get(self.PATH_PREFIX + '/event_types',
                                expect_errors=True)

        self.assertEqual(308, response.status_code)
        self.assertEqual("http://event-endpoint:8009/v2/event_types",
                         response.headers['Location'])

    def test_gnocchi_enabled_without_database_backend_keystone(self):
        self._setup_keystone_mock()
        self._do_test_gnocchi_enabled_without_database_backend()
        self.catalog.url_for.assert_has_calls(
            [mock.call(service_type="metric")])

    def test_gnocchi_enabled_without_database_backend_configoptions(self):
        self._setup_osloconfig_options()
        self._do_test_gnocchi_enabled_without_database_backend()

    def test_alarm_redirect_keystone(self):
        self._setup_keystone_mock()
        self._do_test_alarm_redirect()
        self.catalog.url_for.assert_has_calls(
            [mock.call(service_type="alarming")])

    def test_event_redirect_keystone(self):
        self._setup_keystone_mock()
        self._do_test_event_redirect()
        self.catalog.url_for.assert_has_calls(
            [mock.call(service_type="event")])

    def test_alarm_redirect_configoptions(self):
        self._setup_osloconfig_options()
        self._do_test_alarm_redirect()

    def test_event_redirect_configoptions(self):
        self._setup_osloconfig_options()
        self._do_test_event_redirect()
