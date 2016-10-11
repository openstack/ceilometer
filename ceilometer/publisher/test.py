#
# Copyright 2013 eNovance
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
"""Publish a sample in memory, useful for testing
"""

from ceilometer import publisher


class TestPublisher(publisher.ConfigPublisherBase):
    """Publisher used in unit testing."""

    def __init__(self, conf, parsed_url):
        super(TestPublisher, self).__init__(conf, parsed_url)
        self.samples = []
        self.events = []
        self.calls = 0

    def publish_samples(self, samples):
        """Send a metering message for publishing

        :param samples: Samples from pipeline after transformation
        """
        self.samples.extend(samples)
        self.calls += 1

    def publish_events(self, events):
        """Send an event message for publishing

        :param events: events from pipeline after transformation
        """
        self.events.extend(events)
        self.calls += 1
