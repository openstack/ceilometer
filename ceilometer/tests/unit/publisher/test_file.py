#
# Copyright 2013-2014 eNovance
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
"""Tests for ceilometer/publisher/file.py
"""

import datetime
import logging.handlers
import os
import tempfile

from oslo_utils import netutils
from oslotest import base

from ceilometer.publisher import file
from ceilometer import sample
from ceilometer import service


class TestFilePublisher(base.BaseTestCase):

    test_data = [
        sample.Sample(
            name='test',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='test2',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='test2',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
    ]

    def setUp(self):
        super(TestFilePublisher, self).setUp()
        self.CONF = service.prepare_service([], [])

    def test_file_publisher_maxbytes(self):
        # Test valid configurations
        tempdir = tempfile.mkdtemp()
        name = '%s/log_file' % tempdir
        parsed_url = netutils.urlsplit('file://%s?max_bytes=50&backup_count=3'
                                       % name)
        publisher = file.FilePublisher(self.CONF, parsed_url)
        publisher.publish_samples(self.test_data)

        handler = publisher.publisher_logger.handlers[0]
        self.assertIsInstance(handler,
                              logging.handlers.RotatingFileHandler)
        self.assertEqual([50, name, 3], [handler.maxBytes,
                                         handler.baseFilename,
                                         handler.backupCount])
        # The rotating file gets created since only allow 50 bytes.
        self.assertTrue(os.path.exists('%s.1' % name))

    def test_file_publisher(self):
        # Test missing max bytes, backup count configurations
        tempdir = tempfile.mkdtemp()
        name = '%s/log_file_plain' % tempdir
        parsed_url = netutils.urlsplit('file://%s' % name)
        publisher = file.FilePublisher(self.CONF, parsed_url)
        publisher.publish_samples(self.test_data)

        handler = publisher.publisher_logger.handlers[0]
        self.assertIsInstance(handler,
                              logging.handlers.RotatingFileHandler)
        self.assertEqual([0, name, 0], [handler.maxBytes,
                                        handler.baseFilename,
                                        handler.backupCount])
        # Test the content is corrected saved in the file
        self.assertTrue(os.path.exists(name))
        with open(name, 'r') as f:
            content = f.read()
        for sample_item in self.test_data:
            self.assertIn(sample_item.id, content)
            self.assertIn(sample_item.timestamp, content)

    def test_file_publisher_invalid(self):
        # Test invalid max bytes, backup count configurations
        tempdir = tempfile.mkdtemp()
        parsed_url = netutils.urlsplit(
            'file://%s/log_file_bad'
            '?max_bytes=yus&backup_count=5y' % tempdir)
        publisher = file.FilePublisher(self.CONF, parsed_url)
        publisher.publish_samples(self.test_data)

        self.assertIsNone(publisher.publisher_logger)
