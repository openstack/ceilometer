#
# Copyright 2013 IBM Corp
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
import logging.handlers
import os
import tempfile

from oslotest import base

from ceilometer.dispatcher import file
from ceilometer.publisher import utils
from ceilometer import service


class TestDispatcherFile(base.BaseTestCase):

    def setUp(self):
        super(TestDispatcherFile, self).setUp()
        self.CONF = service.prepare_service([], [])

    def test_file_dispatcher_with_all_config(self):
        # Create a temporaryFile to get a file name
        tf = tempfile.NamedTemporaryFile('r')
        filename = tf.name
        tf.close()

        self.CONF.dispatcher_file.file_path = filename
        self.CONF.dispatcher_file.max_bytes = 50
        self.CONF.dispatcher_file.backup_count = 5
        dispatcher = file.FileDispatcher(self.CONF)

        # The number of the handlers should be 1
        self.assertEqual(1, len(dispatcher.log.handlers))
        # The handler should be RotatingFileHandler
        handler = dispatcher.log.handlers[0]
        self.assertIsInstance(handler,
                              logging.handlers.RotatingFileHandler)

        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               }
        msg['message_signature'] = utils.compute_signature(
            msg, self.CONF.publisher.telemetry_secret,
        )

        # The record_metering_data method should exist
        # and not produce errors.
        dispatcher.record_metering_data(msg)
        # After the method call above, the file should have been created.
        self.assertTrue(os.path.exists(handler.baseFilename))

    def test_file_dispatcher_with_path_only(self):
        # Create a temporaryFile to get a file name
        tf = tempfile.NamedTemporaryFile('r')
        filename = tf.name
        tf.close()

        self.CONF.dispatcher_file.file_path = filename
        self.CONF.dispatcher_file.max_bytes = 0
        self.CONF.dispatcher_file.backup_count = 0
        dispatcher = file.FileDispatcher(self.CONF)

        # The number of the handlers should be 1
        self.assertEqual(1, len(dispatcher.log.handlers))
        # The handler should be RotatingFileHandler
        handler = dispatcher.log.handlers[0]
        self.assertIsInstance(handler,
                              logging.FileHandler)

        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               }
        msg['message_signature'] = utils.compute_signature(
            msg, self.CONF.publisher.telemetry_secret,
        )

        # The record_metering_data method should exist and not produce errors.
        dispatcher.record_metering_data(msg)
        # After the method call above, the file should have been created.
        self.assertTrue(os.path.exists(handler.baseFilename))

    def test_file_dispatcher_with_no_path(self):
        self.CONF.dispatcher_file.file_path = None
        dispatcher = file.FileDispatcher(self.CONF)

        # The log should be None
        self.assertIsNone(dispatcher.log)
