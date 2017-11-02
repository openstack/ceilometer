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

from ceilometer.polling import manager
from ceilometer import service
from ceilometer.tests import base


class PollingTestCase(base.BaseTestCase):

    def setUp(self):
        super(PollingTestCase, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.poll_cfg = {'sources': [{'name': 'test_source',
                                      'interval': 600,
                                      'meters': ['a']}]}

    def _build_and_set_new_polling(self):
        name = self.cfg2file(self.poll_cfg)
        self.CONF.set_override('cfg_file', name, group='polling')

    def test_no_name(self):
        del self.poll_cfg['sources'][0]['name']
        self._build_and_set_new_polling()
        self.assertRaises(manager.PollingException,
                          manager.PollingManager, self.CONF)

    def test_no_interval(self):
        del self.poll_cfg['sources'][0]['interval']
        self._build_and_set_new_polling()
        self.assertRaises(manager.PollingException,
                          manager.PollingManager, self.CONF)

    def test_invalid_string_interval(self):
        self.poll_cfg['sources'][0]['interval'] = 'string'
        self._build_and_set_new_polling()
        self.assertRaises(manager.PollingException,
                          manager.PollingManager, self.CONF)

    def test_get_interval(self):
        self._build_and_set_new_polling()
        poll_manager = manager.PollingManager(self.CONF)
        source = poll_manager.sources[0]
        self.assertEqual(600, source.get_interval())

    def test_invalid_resources(self):
        self.poll_cfg['sources'][0]['resources'] = {'invalid': 1}
        self._build_and_set_new_polling()
        self.assertRaises(manager.PollingException,
                          manager.PollingManager, self.CONF)

    def test_resources(self):
        resources = ['test1://', 'test2://']
        self.poll_cfg['sources'][0]['resources'] = resources
        self._build_and_set_new_polling()
        poll_manager = manager.PollingManager(self.CONF)
        self.assertEqual(resources, poll_manager.sources[0].resources)

    def test_no_resources(self):
        self._build_and_set_new_polling()
        poll_manager = manager.PollingManager(self.CONF)
        self.assertEqual(0, len(poll_manager.sources[0].resources))

    def test_check_meters_include_exclude_same(self):
        self.poll_cfg['sources'][0]['meters'] = ['a', '!a']
        self._build_and_set_new_polling()
        self.assertRaises(manager.PollingException,
                          manager.PollingManager, self.CONF)

    def test_check_meters_include_exclude(self):
        self.poll_cfg['sources'][0]['meters'] = ['a', '!b']
        self._build_and_set_new_polling()
        self.assertRaises(manager.PollingException,
                          manager.PollingManager, self.CONF)

    def test_check_meters_wildcard_included(self):
        self.poll_cfg['sources'][0]['meters'] = ['a', '*']
        self._build_and_set_new_polling()
        self.assertRaises(manager.PollingException,
                          manager.PollingManager, self.CONF)
