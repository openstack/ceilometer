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

import os
import tempfile

from oslotest import base
import yaml

from ceilometer import pipeline
from ceilometer import service


class PollingTestCase(base.BaseTestCase):

    def cfg2file(self, data):
        self.tmp_cfg.write(yaml.safe_dump(data))
        self.tmp_cfg.close()
        return self.tmp_cfg.name

    def setUp(self):
        super(PollingTestCase, self).setUp()
        self.CONF = service.prepare_service([], [])

        self.tmp_cfg = tempfile.NamedTemporaryFile(mode='w', delete=False)
        self.poll_cfg = {'sources': [{'name': 'test_source',
                                      'interval': 600,
                                      'meters': ['a']}]}

    def tearDown(self):
        os.unlink(self.tmp_cfg.name)
        super(PollingTestCase, self).tearDown()

    def test_no_name(self):
        del self.poll_cfg['sources'][0]['name']
        self.assertRaises(pipeline.PipelineException,
                          pipeline.PollingManager,
                          self.CONF, self.cfg2file(self.poll_cfg))

    def test_no_interval(self):
        del self.poll_cfg['sources'][0]['interval']
        self.assertRaises(pipeline.PipelineException,
                          pipeline.PollingManager,
                          self.CONF, self.cfg2file(self.poll_cfg))

    def test_invalid_string_interval(self):
        self.poll_cfg['sources'][0]['interval'] = 'string'
        self.assertRaises(pipeline.PipelineException,
                          pipeline.PollingManager,
                          self.CONF, self.cfg2file(self.poll_cfg))

    def test_get_interval(self):
        poll_manager = pipeline.PollingManager(
            self.CONF, self.cfg2file(self.poll_cfg))
        source = poll_manager.sources[0]
        self.assertEqual(600, source.get_interval())

    def test_invalid_resources(self):
        self.poll_cfg['sources'][0]['resources'] = {'invalid': 1}
        self.assertRaises(pipeline.PipelineException,
                          pipeline.PollingManager,
                          self.CONF, self.cfg2file(self.poll_cfg))

    def test_resources(self):
        resources = ['test1://', 'test2://']
        self.poll_cfg['sources'][0]['resources'] = resources
        poll_manager = pipeline.PollingManager(
            self.CONF, self.cfg2file(self.poll_cfg))
        self.assertEqual(resources, poll_manager.sources[0].resources)

    def test_no_resources(self):
        poll_manager = pipeline.PollingManager(
            self.CONF, self.cfg2file(self.poll_cfg))
        self.assertEqual(0, len(poll_manager.sources[0].resources))

    def test_check_meters_include_exclude_same(self):
        self.poll_cfg['sources'][0]['meters'] = ['a', '!a']
        self.assertRaises(pipeline.PipelineException,
                          pipeline.PollingManager,
                          self.CONF, self.cfg2file(self.poll_cfg))

    def test_check_meters_include_exclude(self):
        self.poll_cfg['sources'][0]['meters'] = ['a', '!b']
        self.assertRaises(pipeline.PipelineException,
                          pipeline.PollingManager,
                          self.CONF, self.cfg2file(self.poll_cfg))

    def test_check_meters_wildcard_included(self):
        self.poll_cfg['sources'][0]['meters'] = ['a', '*']
        self.assertRaises(pipeline.PipelineException,
                          pipeline.PollingManager,
                          self.CONF, self.cfg2file(self.poll_cfg))
