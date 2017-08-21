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

from oslotest import base

from ceilometer.telemetry import notifications

NOTIFICATION = {
    u'_context_domain': None,
    u'_context_request_id': u'req-da91b4bf-d2b5-43ae-8b66-c7752e72726d',
    'event_type': u'telemetry.api',
    'timestamp': u'2015-06-19T09:19:35.786893',
    u'_context_auth_token': None,
    u'_context_read_only': False,
    'payload': {'samples':
                [{'counter_name': u'instance100',
                  u'user_id': u'e1d870e51c7340cb9d555b15cbfcaec2',
                  u'resource_id': u'instance',
                  u'timestamp': u'2015-06-19T09: 19: 35.785330',
                  u'message_signature': u'fake_signature1',
                  u'resource_metadata': {u'foo': u'bar'},
                  u'source': u'30be1fc9a03c4e94ab05c403a8a377f2: openstack',
                  u'counter_unit': u'instance',
                  u'counter_volume': 1.0,
                  u'project_id': u'30be1fc9a03c4e94ab05c403a8a377f2',
                  u'message_id': u'4d865c6e-1664-11e5-9d41-0819a6cff905',
                  u'counter_type': u'gauge'},
                 {u'counter_name': u'instance100',
                  u'user_id': u'e1d870e51c7340cb9d555b15cbfcaec2',
                  u'resource_id': u'instance',
                  u'timestamp': u'2015-06-19T09: 19: 35.785330',
                  u'message_signature': u'fake_signature12',
                  u'resource_metadata': {u'foo': u'bar'},
                  u'source': u'30be1fc9a03c4e94ab05c403a8a377f2: openstack',
                  u'counter_unit': u'instance',
                  u'counter_volume': 1.0,
                  u'project_id': u'30be1fc9a03c4e94ab05c403a8a377f2',
                  u'message_id': u'4d866da8-1664-11e5-9d41-0819a6cff905',
                  u'counter_type': u'gauge'}]},
    u'_context_resource_uuid': None,
    u'_context_user_identity': u'fake_user_identity---',
    u'_context_show_deleted': False,
    u'_context_tenant': u'30be1fc9a03c4e94ab05c403a8a377f2',
    'priority': 'info',
    u'_context_is_admin': True,
    u'_context_project_domain': None,
    u'_context_user': u'e1d870e51c7340cb9d555b15cbfcaec2',
    u'_context_user_domain': None,
    'publisher_id': u'ceilometer.api',
    'message_id': u'939823de-c242-45a2-a399-083f4d6a8c3e'
}


class TelemetryIpcTestCase(base.BaseTestCase):

    def test_process_notification(self):
        sample_creation = notifications.TelemetryIpc(None)
        samples = list(sample_creation.process_notification(NOTIFICATION))
        self.assertEqual(2, len(samples))
        payload = NOTIFICATION["payload"]['samples']
        for index, sample in enumerate(samples):
            self.assertEqual(payload[index]["user_id"], sample.user_id)
            self.assertEqual(payload[index]["counter_name"], sample.name)
            self.assertEqual(payload[index]["resource_id"], sample.resource_id)
            self.assertEqual(payload[index]["timestamp"], sample.timestamp)
            self.assertEqual(payload[index]["resource_metadata"],
                             sample.resource_metadata)
            self.assertEqual(payload[index]["counter_volume"], sample.volume)
            self.assertEqual(payload[index]["source"], sample.source)
            self.assertEqual(payload[index]["counter_type"], sample.type)
            self.assertEqual(payload[index]["message_id"], sample.id)
            self.assertEqual(payload[index]["counter_unit"], sample.unit)
