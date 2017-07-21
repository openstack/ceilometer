#
# Copyright 2013 Red Hat, Inc
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
"""Test listing raw events.
"""

import copy
import datetime
import os

import fixtures
import mock
from oslo_utils import fileutils
from oslo_utils import timeutils
import six

from ceilometer.tests.functional.api import v2


class TestPostSamples(v2.FunctionalTest):
    def fake_notifier_sample(self, ctxt, event_type, payload):
        samples = payload['samples']
        for m in samples:
            del m['message_signature']
        self.published.append(samples)

    def _make_app(self, enable_acl=False):
        content = ('{"context_is_project": "project_id:%(project_id)s",'
                   '"default" : "!",'
                   '"telemetry:create_samples": ""}')
        if six.PY3:
            content = content.encode('utf-8')
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='policy',
                                                    suffix='.json')
        self.CONF.set_override("policy_file", self.tempfile,
                               group='oslo_policy')
        return super(TestPostSamples, self)._make_app()

    def tearDown(self):
        os.remove(self.tempfile)
        super(TestPostSamples, self).tearDown()

    def setUp(self):
        self.published = []
        notifier = mock.Mock()
        notifier.sample.side_effect = self.fake_notifier_sample
        self.useFixture(fixtures.MockPatch('oslo_messaging.Notifier',
                                           return_value=notifier))
        super(TestPostSamples, self).setUp()

    def test_one(self):
        s1 = [{'counter_name': 'apples',
               'counter_type': 'gauge',
               'counter_unit': 'instance',
               'counter_volume': 1,
               'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
               'project_id': '35b17138-b364-4e6a-a131-8f3099c5be68',
               'user_id': 'efd87807-12d2-4b38-9c70-5f5c2ac427ff',
               'resource_metadata': {'name1': 'value1',
                                     'name2': 'value2'}}]
        data = self.post_json('/meters/apples/', s1)

        # timestamp not given so it is generated.
        s1[0]['timestamp'] = data.json[0]['timestamp']
        # Ignore message id that is randomly generated
        s1[0]['message_id'] = data.json[0]['message_id']
        # source is generated if not provided.
        s1[0]['source'] = '%s:openstack' % s1[0]['project_id']

        self.assertEqual(s1, data.json)
        s1[0]["monotonic_time"] = None
        self.assertEqual(s1[0], self.published[0][0])

    def test_nested_metadata(self):
        s1 = [{'counter_name': 'apples',
               'counter_type': 'gauge',
               'counter_unit': 'instance',
               'counter_volume': 1,
               'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
               'project_id': '35b17138-b364-4e6a-a131-8f3099c5be68',
               'user_id': 'efd87807-12d2-4b38-9c70-5f5c2ac427ff',
               'resource_metadata': {'nest.name1': 'value1',
                                     'name2': 'value2',
                                     'nest.name2': 'value3'}}]

        data = self.post_json('/meters/apples/', s1)

        # timestamp not given so it is generated.
        s1[0]['timestamp'] = data.json[0]['timestamp']
        # Ignore message id that is randomly generated
        s1[0]['message_id'] = data.json[0]['message_id']
        # source is generated if not provided.
        s1[0]['source'] = '%s:openstack' % s1[0]['project_id']

        unwound = copy.copy(s1[0])
        unwound['resource_metadata'] = {'nest': {'name1': 'value1',
                                                 'name2': 'value3'},
                                        'name2': 'value2'}
        unwound["monotonic_time"] = None
        # only the published sample should be unwound, not the representation
        # in the API response
        self.assertEqual(s1[0], data.json[0])
        self.assertEqual(unwound, self.published[0][0])

    def test_invalid_counter_type(self):
        s1 = [{'counter_name': 'my_counter_name',
               'counter_type': 'INVALID_TYPE',
               'counter_unit': 'instance',
               'counter_volume': 1,
               'source': 'closedstack',
               'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
               'project_id': '35b17138-b364-4e6a-a131-8f3099c5be68',
               'user_id': 'efd87807-12d2-4b38-9c70-5f5c2ac427ff',
               'resource_metadata': {'name1': 'value1',
                                     'name2': 'value2'}}]

        data = self.post_json('/meters/my_counter_name/', s1,
                              expect_errors=True)

        self.assertEqual(400, data.status_int)
        self.assertEqual(0, len(self.published))

    def test_messsage_id_provided(self):
        """Do not accept sample with message_id."""
        s1 = [{'counter_name': 'my_counter_name',
               'counter_type': 'gauge',
               'counter_unit': 'instance',
               'counter_volume': 1,
               'message_id': 'evil',
               'source': 'closedstack',
               'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
               'project_id': '35b17138-b364-4e6a-a131-8f3099c5be68',
               'user_id': 'efd87807-12d2-4b38-9c70-5f5c2ac427ff',
               'resource_metadata': {'name1': 'value1',
                                     'name2': 'value2'}}]

        data = self.post_json('/meters/my_counter_name/', s1,
                              expect_errors=True)

        self.assertEqual(400, data.status_int)
        self.assertEqual(0, len(self.published))

    def test_wrong_project_id(self):
        """Do not accept cross posting samples to different projects."""
        s1 = [{'counter_name': 'my_counter_name',
               'counter_type': 'gauge',
               'counter_unit': 'instance',
               'counter_volume': 1,
               'source': 'closedstack',
               'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
               'project_id': '35b17138-b364-4e6a-a131-8f3099c5be68',
               'user_id': 'efd87807-12d2-4b38-9c70-5f5c2ac427ff',
               'resource_metadata': {'name1': 'value1',
                                     'name2': 'value2'}}]

        data = self.post_json('/meters/my_counter_name/', s1,
                              expect_errors=True,
                              headers={
                                  "X-Roles": "Member",
                                  "X-Tenant-Name": "lu-tenant",
                                  "X-Project-Id":
                                  "bc23a9d531064583ace8f67dad60f6bb",
                              })

        self.assertEqual(400, data.status_int)
        self.assertEqual(0, len(self.published))

    def test_multiple_samples(self):
        """Send multiple samples.

        The usecase here is to reduce the chatter and send the counters
        at a slower cadence.
        """
        samples = []
        for x in range(6):
            dt = datetime.datetime(2012, 8, 27, x, 0, tzinfo=None)
            s = {'counter_name': 'apples',
                 'counter_type': 'gauge',
                 'counter_unit': 'instance',
                 'counter_volume': float(x * 3),
                 'source': 'evil',
                 'timestamp': dt.isoformat(),
                 'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
                 'project_id': '35b17138-b364-4e6a-a131-8f3099c5be68',
                 'user_id': 'efd87807-12d2-4b38-9c70-5f5c2ac427ff',
                 'resource_metadata': {'name1': str(x),
                                       'name2': str(x + 4)}}
            samples.append(s)

        data = self.post_json('/meters/apples/', samples)

        for x, s in enumerate(samples):
            # source is modified to include the project_id.
            s['source'] = '%s:%s' % (s['project_id'],
                                     s['source'])
            # Ignore message id that is randomly generated
            s['message_id'] = data.json[x]['message_id']

            # remove tzinfo to compare generated timestamp
            # with the provided one
            c = data.json[x]
            timestamp = timeutils.parse_isotime(c['timestamp'])
            c['timestamp'] = timestamp.replace(tzinfo=None).isoformat()

            # do the same on the pipeline
            msg = self.published[0][x]
            timestamp = timeutils.parse_isotime(msg['timestamp'])
            msg['timestamp'] = timestamp.replace(tzinfo=None).isoformat()

            self.assertEqual(s, c)
            s["monotonic_time"] = None
            self.assertEqual(s, self.published[0][x])

    def test_missing_mandatory_fields(self):
        """Do not accept posting samples with missing mandatory fields."""
        s1 = [{'counter_name': 'my_counter_name',
               'counter_type': 'gauge',
               'counter_unit': 'instance',
               'counter_volume': 1,
               'source': 'closedstack',
               'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
               'project_id': '35b17138-b364-4e6a-a131-8f3099c5be68',
               'user_id': 'efd87807-12d2-4b38-9c70-5f5c2ac427ff',
               'resource_metadata': {'name1': 'value1',
                                     'name2': 'value2'}}]

        # one by one try posting without a mandatory field.
        for m in ['counter_volume', 'counter_unit', 'counter_type',
                  'resource_id', 'counter_name']:
            s_broke = copy.copy(s1)
            del s_broke[0][m]
            print('posting without %s' % m)
            data = self.post_json('/meters/my_counter_name', s_broke,
                                  expect_errors=True)
            self.assertEqual(400, data.status_int)

    def test_multiple_project_id_and_admin(self):
        """Allow admin is allowed to set multiple project_id."""
        s1 = [{'counter_name': 'my_counter_name',
               'counter_type': 'gauge',
               'counter_unit': 'instance',
               'counter_volume': 1,
               'source': 'closedstack',
               'project_id': '35b17138-b364-4e6a-a131-8f3099c5be68',
               'user_id': 'efd87807-12d2-4b38-9c70-5f5c2ac427ff',
               'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
               },
              {'counter_name': 'my_counter_name',
               'counter_type': 'gauge',
               'counter_unit': 'instance',
               'counter_volume': 2,
               'source': 'closedstack',
               'project_id': '4af38dca-f6fc-11e2-94f5-14dae9283f29',
               'user_id': 'efd87807-12d2-4b38-9c70-5f5c2ac427ff',
               'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
               'resource_metadata': {'name1': 'value1',
                                     'name2': 'value2'}}]
        data = self.post_json('/meters/my_counter_name/', s1,
                              headers={"X-Roles": "admin"})

        self.assertEqual(201, data.status_int)
        for x, s in enumerate(s1):
            # source is modified to include the project_id.
            s['source'] = '%s:%s' % (s['project_id'],
                                     'closedstack')
            # Ignore message id that is randomly generated
            s['message_id'] = data.json[x]['message_id']
            # timestamp not given so it is generated.
            s['timestamp'] = data.json[x]['timestamp']
            s.setdefault('resource_metadata', dict())
            self.assertEqual(s, data.json[x])
            s['monotonic_time'] = None
            self.assertEqual(s, self.published[0][x])

    def test_multiple_samples_multiple_sources(self):
        """Test posting with special conditions.

        Do accept a single post with some multiples sources with some of them
        null.
        """
        s1 = [{'counter_name': 'my_counter_name',
               'counter_type': 'gauge',
               'counter_unit': 'instance',
               'counter_volume': 1,
               'source': 'paperstack',
               'project_id': '35b17138-b364-4e6a-a131-8f3099c5be68',
               'user_id': 'efd87807-12d2-4b38-9c70-5f5c2ac427ff',
               'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
               },
              {'counter_name': 'my_counter_name',
               'counter_type': 'gauge',
               'counter_unit': 'instance',
               'counter_volume': 5,
               'source': 'waterstack',
               'project_id': '35b17138-b364-4e6a-a131-8f3099c5be68',
               'user_id': 'efd87807-12d2-4b38-9c70-5f5c2ac427ff',
               'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
               },
              {'counter_name': 'my_counter_name',
               'counter_type': 'gauge',
               'counter_unit': 'instance',
               'counter_volume': 2,
               'project_id': '35b17138-b364-4e6a-a131-8f3099c5be68',
               'user_id': 'efd87807-12d2-4b38-9c70-5f5c2ac427ff',
               'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
               'resource_metadata': {'name1': 'value1',
                                     'name2': 'value2'}}]
        data = self.post_json('/meters/my_counter_name/', s1,
                              expect_errors=True)
        self.assertEqual(201, data.status_int)
        for x, s in enumerate(s1):
            # source is modified to include the project_id.
            s['source'] = '%s:%s' % (
                s['project_id'],
                s.get('source', self.CONF.sample_source)
            )
            # Ignore message id that is randomly generated
            s['message_id'] = data.json[x]['message_id']
            # timestamp not given so it is generated.
            s['timestamp'] = data.json[x]['timestamp']
            s.setdefault('resource_metadata', dict())
            self.assertEqual(s, data.json[x])
            s['monotonic_time'] = None
            self.assertEqual(s, self.published[0][x])

    def test_missing_project_user_id(self):
        """Ensure missing project & user IDs are defaulted appropriately."""
        s1 = [{'counter_name': 'my_counter_name',
               'counter_type': 'gauge',
               'counter_unit': 'instance',
               'counter_volume': 1,
               'source': 'closedstack',
               'resource_id': 'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
               'resource_metadata': {'name1': 'value1',
                                     'name2': 'value2'}}]

        project_id = 'bc23a9d531064583ace8f67dad60f6bb'
        user_id = 'fd87807-12d2-4b38-9c70-5f5c2ac427ff'
        data = self.post_json('/meters/my_counter_name/', s1,
                              expect_errors=True,
                              headers={
                                  'X-Roles': 'chief-bottle-washer',
                                  'X-Project-Id': project_id,
                                  'X-User-Id': user_id,
                              })

        self.assertEqual(201, data.status_int)
        for x, s in enumerate(s1):
            # source is modified to include the project_id.
            s['source'] = '%s:%s' % (project_id,
                                     s['source'])
            # Ignore message id that is randomly generated
            s['message_id'] = data.json[x]['message_id']
            # timestamp not given so it is generated.
            s['timestamp'] = data.json[x]['timestamp']
            s['user_id'] = user_id
            s['project_id'] = project_id

            self.assertEqual(s, data.json[x])

            s['monotonic_time'] = None
            self.assertEqual(s, self.published[0][x])
