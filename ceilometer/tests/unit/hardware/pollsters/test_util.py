#
# Copyright 2013 Intel Corp
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

from oslo_utils import netutils

from ceilometer.hardware.pollsters import util
from ceilometer import sample
from ceilometer.tests import base as test_base


class TestPollsterUtils(test_base.BaseTestCase):
    def setUp(self):
        super(TestPollsterUtils, self).setUp()
        self.host_url = netutils.urlsplit("snmp://127.0.0.1:161")

    def test_make_sample(self):
        s = util.make_sample_from_host(self.host_url,
                                       name='test',
                                       sample_type=sample.TYPE_GAUGE,
                                       unit='B',
                                       volume=1,
                                       res_metadata={
                                           'metakey': 'metaval',
                                       })
        self.assertEqual('127.0.0.1', s.resource_id)
        self.assertIn('snmp://127.0.0.1:161', s.resource_metadata.values())
        self.assertIn('metakey', s.resource_metadata.keys())

    def test_make_sample_extra(self):
        extra = {
            'project_id': 'project',
            'resource_id': 'resource'
        }
        s = util.make_sample_from_host(self.host_url,
                                       name='test',
                                       sample_type=sample.TYPE_GAUGE,
                                       unit='B',
                                       volume=1,
                                       extra=extra)
        self.assertIsNone(s.user_id)
        self.assertEqual('project', s.project_id)
        self.assertEqual('resource', s.resource_id)
        self.assertEqual({'resource_url': 'snmp://127.0.0.1:161',
                          'project_id': 'project',
                          'resource_id':
                          'resource'},
                         s.resource_metadata)
