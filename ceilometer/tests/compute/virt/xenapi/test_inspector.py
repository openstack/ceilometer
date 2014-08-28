# Copyright 2014 Intel
#
# Author: Ren Qiaowei <qiaowei.ren@intel.com>
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
"""Tests for xenapi inspector.
"""

import mock
from oslotest import base

from ceilometer.compute.virt.xenapi import inspector as xenapi_inspector


class TestXenapiInspection(base.BaseTestCase):

    def setUp(self):
        api_session = mock.Mock()
        xenapi_inspector.get_api_session = mock.Mock(return_value=api_session)
        self.inspector = xenapi_inspector.XenapiInspector()

        super(TestXenapiInspection, self).setUp()

    def test_inspect_instances(self):
        vms = {
            'ref': {
                'name_label': 'fake_name',
                'other_config': {'nova_uuid': 'fake_uuid', },
            }
        }

        session = self.inspector.session
        with mock.patch.object(session, 'xenapi_request',
                               return_value=vms):
            inspected_instances = list(self.inspector.inspect_instances())
            inspected_instance = inspected_instances[0]
            self.assertEqual('fake_name', inspected_instance.name)
            self.assertEqual('fake_uuid', inspected_instance.UUID)
