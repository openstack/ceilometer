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
from unittest import mock

from ceilometer.polling import manager
from ceilometer import service
from ceilometer.share import discovery
from ceilometer.share import manila
from ceilometer.tests import base
from ceilometer.tests.unit import fakes


class _BaseTestSharePollster(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.addCleanup(mock.patch.stopall)
        self.CONF = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, self.CONF)


class TestShareStatusPollster(_BaseTestSharePollster):

    def setUp(self):
        super().setUp()
        self.pollster = manila.ShareStatusPollster(self.CONF)
        self.shares = fakes.FakeSDKManilaClient.default_shares

    def test_share_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=self.shares))

        self.assertEqual(len(self.shares), len(samples))
        # Verify metadata fields are correctly extracted
        self.assertEqual('my-share-1', samples[0].resource_metadata['name'])
        self.assertEqual('az-1',
                         samples[0].resource_metadata['availability_zone'])
        # Verify share_protocol is renamed to protocol
        self.assertEqual('NFS', samples[0].resource_metadata['protocol'])
        self.assertNotIn('share_protocol', samples[0].resource_metadata)

    def test_share_status_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=self.shares))

        # available = 1, creating = 2, error = 4
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(2, samples[1].volume)
        self.assertEqual(4, samples[2].volume)

    def test_get_share_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=self.shares))
        self.assertEqual({'manila.share.status'},
                         {s.name for s in samples})

    def test_share_discovery(self):
        discovered_shares = discovery.ShareDiscovery(
            self.CONF).discover(self.manager)
        self.assertEqual(len(fakes.FakeSDKManilaClient.default_shares),
                         len(list(discovered_shares)))


class TestShareSizePollster(_BaseTestSharePollster):

    def setUp(self):
        super().setUp()
        self.pollster = manila.ShareSizePollster(self.CONF)
        self.shares = fakes.FakeSDKManilaClient.default_shares

    def test_share_size_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=self.shares))
        self.assertEqual(100, samples[0].volume)
        self.assertEqual(50, samples[1].volume)
        self.assertEqual(200, samples[2].volume)

    def test_get_share_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=self.shares))
        self.assertEqual({'manila.share.size'},
                         {s.name for s in samples})


class TestSharePollsterUnknownStatus(_BaseTestSharePollster):

    def test_unknown_share_status(self):
        pollster = manila.ShareStatusPollster(self.CONF)
        samples = list(pollster.get_samples(
            self.manager, {}, resources=[fakes.SHARE_UNKNOWN_STATUS]))
        self.assertEqual(1, len(samples))
        self.assertEqual(-1, samples[0].volume)
