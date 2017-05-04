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
from oslo_config import fixture

from ceilometer import collector
from ceilometer import dispatcher
from ceilometer.publisher import utils
from ceilometer import service
from ceilometer.tests import base


class FakeDispatcher(dispatcher.EventDispatcherBase):
    def __init__(self, conf):
        super(FakeDispatcher, self).__init__(conf)
        self.events = []

    def record_events(self, events):
        super(FakeDispatcher, self).record_events(events)
        self.events.extend(events)


class TestEventDispatcherVerifier(base.BaseTestCase):
    def setUp(self):
        super(TestEventDispatcherVerifier, self).setUp()
        conf = service.prepare_service([], [])
        self.conf = self.useFixture(fixture.Config(conf)).conf
        self.conf.import_opt('telemetry_secret',
                             'ceilometer.publisher.utils',
                             'publisher')
        self.conf.set_override("event_dispatchers", ['file'])
        self.useFixture(fixtures.MockPatch(
            'ceilometer.dispatcher.file.FileDispatcher',
            new=FakeDispatcher))

    @mock.patch('ceilometer.publisher.utils.verify_signature')
    def test_sample_with_bad_signature(self, mocked_verify):
        def _fake_verify(ev, secret):
            return ev.get('message_signature') != 'bad_signature'
        mocked_verify.side_effect = _fake_verify
        sample = {"payload": [{"message_signature": "bad_signature"}]}
        manager = dispatcher.load_dispatcher_manager(self.conf)[1]
        v = collector.EventEndpoint("secret", manager)
        v.sample([sample])
        self.assertEqual([], manager['file'].obj.events)
        del sample['payload'][0]['message_signature']
        sample['payload'][0]['message_signature'] = utils.compute_signature(
            sample['payload'][0], "secret")
        v.sample([sample])
        self.assertEqual(sample['payload'], manager['file'].obj.events)
