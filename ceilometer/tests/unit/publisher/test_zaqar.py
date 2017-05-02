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

import datetime
import mock
from oslotest import base
from six.moves.urllib import parse as urlparse
import uuid

from ceilometer.event.storage import models as event
from ceilometer.publisher import zaqar
from ceilometer import sample
from ceilometer import service


class TestZaqarPublisher(base.BaseTestCase):

    resource_id = str(uuid.uuid4())

    sample_data = [
        sample.Sample(
            name='alpha',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id=resource_id,
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='beta',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id=resource_id,
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='gamma',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id=resource_id,
            timestamp=datetime.datetime.now().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
    ]

    event_data = [event.Event(
        message_id=str(uuid.uuid4()), event_type='event_%d' % i,
        generated=datetime.datetime.utcnow().isoformat(),
        traits=[], raw={'payload': {'some': 'aa'}}) for i in range(3)]

    def setUp(self):
        super(TestZaqarPublisher, self).setUp()
        self.CONF = service.prepare_service([], [])

    def test_zaqar_publisher_config(self):
        """Test publisher config parameters."""
        parsed_url = urlparse.urlparse('zaqar://')
        self.assertRaises(ValueError, zaqar.ZaqarPublisher,
                          self.CONF, parsed_url)

        parsed_url = urlparse.urlparse('zaqar://?queue=foo&ttl=bar')
        self.assertRaises(ValueError, zaqar.ZaqarPublisher,
                          self.CONF, parsed_url)

        parsed_url = urlparse.urlparse('zaqar://?queue=foo&ttl=60')
        publisher = zaqar.ZaqarPublisher(self.CONF, parsed_url)
        self.assertEqual(60, publisher.ttl)

        parsed_url = urlparse.urlparse('zaqar://?queue=foo')
        publisher = zaqar.ZaqarPublisher(self.CONF, parsed_url)
        self.assertEqual(3600, publisher.ttl)
        self.assertEqual('foo', publisher.queue_name)

    @mock.patch('zaqarclient.queues.v2.queues.Queue')
    def test_zaqar_post_samples(self, mock_queue):
        """Test publisher post."""
        parsed_url = urlparse.urlparse('zaqar://?queue=foo')
        publisher = zaqar.ZaqarPublisher(self.CONF, parsed_url)
        mock_post = mock.Mock()
        mock_queue.return_value = mock_post

        publisher.publish_samples(self.sample_data)

        mock_queue.assert_called_once_with(mock.ANY, 'foo')
        self.assertEqual(
            3, len(mock_post.post.call_args_list[0][0][0]))
        self.assertEqual(
            mock_post.post.call_args_list[0][0][0][0]['body'],
            self.sample_data[0].as_dict())

    @mock.patch('zaqarclient.queues.v2.queues.Queue')
    def test_zaqar_post_events(self, mock_queue):
        """Test publisher post."""
        parsed_url = urlparse.urlparse('zaqar://?queue=foo')
        publisher = zaqar.ZaqarPublisher(self.CONF, parsed_url)
        mock_post = mock.Mock()
        mock_queue.return_value = mock_post

        publisher.publish_events(self.event_data)

        mock_queue.assert_called_once_with(mock.ANY, 'foo')
        self.assertEqual(
            3, len(mock_post.post.call_args_list[0][0][0]))
        self.assertEqual(
            mock_post.post.call_args_list[0][0][0][0]['body'],
            self.event_data[0].serialize())
