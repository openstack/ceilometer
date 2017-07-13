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

from six.moves.urllib import parse as urlparse

from ceilometer import keystone_client
from ceilometer import publisher

from zaqarclient.queues.v2 import client as zaqarclient

DEFAULT_TTL = 3600


class ZaqarPublisher(publisher.ConfigPublisherBase):
    """Publish metering data to a Zaqar queue.

    The target queue name must be configured in the ceilometer pipeline
    configuration file. The TTL can also optionally be specified as a query
    argument::

        meter:
            - name: meter_zaqar
            meters:
                - "*"
            sinks:
                - zaqar_sink
        sinks:
            - name: zaqar_sink
            transformers:
            publishers:
                - zaqar://?queue=meter_queue&ttl=1200

    The credentials to access Zaqar must be set in the [zaqar] section in the
    configuration.
    """
    def __init__(self, conf, parsed_url):
        super(ZaqarPublisher, self).__init__(conf, parsed_url)
        options = urlparse.parse_qs(parsed_url.query)
        self.queue_name = options.get('queue', [None])[0]
        if not self.queue_name:
            raise ValueError('Must specify a queue in the zaqar publisher')
        self.ttl = int(options.pop('ttl', [DEFAULT_TTL])[0])
        self._client = None

    @property
    def client(self):
        if self._client is None:
            session = keystone_client.get_session(
                self.conf, group=self.conf.zaqar.auth_section)
            self._client = zaqarclient.Client(session=session)
        return self._client

    def publish_samples(self, samples):
        """Send a metering message for publishing

        :param samples: Samples from pipeline after transformation
        """
        queue = self.client.queue(self.queue_name)
        messages = [{'body': sample.as_dict(), 'ttl': self.ttl}
                    for sample in samples]
        queue.post(messages)

    def publish_events(self, events):
        """Send an event message for publishing

        :param events: events from pipeline after transformation
        """
        queue = self.client.queue(self.queue_name)
        messages = [{'body': event.serialize(), 'ttl': self.ttl}
                    for event in events]
        queue.post(messages)
