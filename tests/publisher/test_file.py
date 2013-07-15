# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance
#
# Author: Julien Danjou <julien@danjou.info>
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
"""Tests for ceilometer/publisher/udp.py
"""

import datetime
import os
import logging
import logging.handlers
from ceilometer import counter
from ceilometer.publisher import file
from ceilometer.tests import base
from ceilometer.openstack.common.network_utils import urlsplit


class TestFilePublisher(base.TestCase):

    test_data = [
        counter.Counter(
            name='test',
            type=counter.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        counter.Counter(
            name='test2',
            type=counter.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        counter.Counter(
            name='test2',
            type=counter.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
    ]

    COUNTER_SOURCE = 'testsource'

    def test_file_publisher(self):
        # Test valid configurations
        parsed_url = urlsplit(
            'file:///tmp/log_file?max_bytes=50&backup_count=3')
        publisher = file.FilePublisher(parsed_url)
        publisher.publish_counters(None,
                                   self.test_data,
                                   self.COUNTER_SOURCE)

        handler = publisher.publisher_logger.handlers[0]
        self.assertTrue(isinstance(handler,
                                   logging.handlers.RotatingFileHandler))
        self.assertEqual([handler.maxBytes, handler.baseFilename,
                          handler.backupCount],
                         [50, '/tmp/log_file', 3])
        # The rotating file gets created since only allow 50 bytes.
        self.assertTrue(os.path.exists('/tmp/log_file.1'))

        # Test missing max bytes, backup count configurations
        parsed_url = urlsplit(
            'file:///tmp/log_file_plain')
        publisher = file.FilePublisher(parsed_url)
        publisher.publish_counters(None,
                                   self.test_data,
                                   self.COUNTER_SOURCE)

        handler = publisher.publisher_logger.handlers[0]
        self.assertTrue(isinstance(handler,
                                   logging.handlers.RotatingFileHandler))
        self.assertEqual([handler.maxBytes, handler.baseFilename,
                          handler.backupCount],
                         [0, '/tmp/log_file_plain', 0])

        # The rotating file gets created since only allow 50 bytes.
        self.assertTrue(os.path.exists('/tmp/log_file_plain'))

        # Test invalid max bytes, backup count configurations
        parsed_url = urlsplit(
            'file:///tmp/log_file_bad?max_bytes=yus&backup_count=5y')
        publisher = file.FilePublisher(parsed_url)
        publisher.publish_counters(None,
                                   self.test_data,
                                   self.COUNTER_SOURCE)

        self.assertIsNone(publisher.publisher_logger)
