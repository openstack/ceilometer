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

import logging
import logging.handlers

from debtcollector import removals
from oslo_config import cfg

from ceilometer import dispatcher

OPTS = [
    cfg.StrOpt('file_path',
               help='Name and the location of the file to record '
                    'meters.'),
    cfg.IntOpt('max_bytes',
               default=0,
               help='The max size of the file.'),
    cfg.IntOpt('backup_count',
               default=0,
               help='The max number of the files to keep.'),
]


@removals.removed_class("FileDispatcher", message="Use file publisher instead",
                        removal_version="9.0.0")
class FileDispatcher(dispatcher.MeterDispatcherBase,
                     dispatcher.EventDispatcherBase):
    """Dispatcher class for recording metering data to a file.

    The dispatcher class which logs each meter and/or event into a file
    configured in ceilometer configuration file. An example configuration may
    look like the following:

    [dispatcher_file]
    file_path = /tmp/meters

    To enable this dispatcher, the following section needs to be present in
    ceilometer.conf file

    [DEFAULT]
    meter_dispatchers = file
    event_dispatchers = file
    """

    def __init__(self, conf):
        super(FileDispatcher, self).__init__(conf)
        self.log = None

        # if the directory and path are configured, then log to the file
        if self.conf.dispatcher_file.file_path:
            dispatcher_logger = logging.Logger('dispatcher.file')
            dispatcher_logger.setLevel(logging.INFO)
            # create rotating file handler which logs meters
            rfh = logging.handlers.RotatingFileHandler(
                self.conf.dispatcher_file.file_path,
                maxBytes=self.conf.dispatcher_file.max_bytes,
                backupCount=self.conf.dispatcher_file.backup_count,
                encoding='utf8')

            rfh.setLevel(logging.INFO)
            # Only wanted the meters to be saved in the file, not the
            # project root logger.
            dispatcher_logger.propagate = False
            dispatcher_logger.addHandler(rfh)
            self.log = dispatcher_logger

    def record_metering_data(self, data):
        if self.log:
            self.log.info(data)

    def record_events(self, events):
        if self.log:
            self.log.info(events)
