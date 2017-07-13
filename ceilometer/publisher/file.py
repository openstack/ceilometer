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

from oslo_log import log
from six.moves.urllib import parse as urlparse

from ceilometer import publisher

LOG = log.getLogger(__name__)


class FilePublisher(publisher.ConfigPublisherBase):
    """Publisher metering data to file.

    The file publisher pushes metering data into a file. The file name and
    location should be configured in ceilometer pipeline configuration file.
    If a file name and location is not specified, this File Publisher will not
    log any meters other than log a warning in Ceilometer log file.

    To enable this publisher, add the following section to the
    /etc/ceilometer/pipeline.yaml file or simply add it to an existing
    pipeline::

        -
            name: meter_file
            meters:
                - "*"
            publishers:
                - file:///var/test?max_bytes=10000000&backup_count=5

    File path is required for this publisher to work properly. If max_bytes
    or backup_count is missing, FileHandler will be used to save the metering
    data. If max_bytes and backup_count are present, RotatingFileHandler will
    be used to save the metering data.
    """

    def __init__(self, conf, parsed_url):
        super(FilePublisher, self).__init__(conf, parsed_url)

        self.publisher_logger = None
        path = parsed_url.path
        if not path:
            LOG.error('The path for the file publisher is required')
            return

        rfh = None
        max_bytes = 0
        backup_count = 0
        # Handling other configuration options in the query string
        if parsed_url.query:
            params = urlparse.parse_qs(parsed_url.query)
            if params.get('max_bytes') and params.get('backup_count'):
                try:
                    max_bytes = int(params.get('max_bytes')[0])
                    backup_count = int(params.get('backup_count')[0])
                except ValueError:
                    LOG.error('max_bytes and backup_count should be '
                              'numbers.')
                    return
        # create rotating file handler
        rfh = logging.handlers.RotatingFileHandler(
            path, encoding='utf8', maxBytes=max_bytes,
            backupCount=backup_count)

        self.publisher_logger = logging.Logger('publisher.file')
        self.publisher_logger.propagate = False
        self.publisher_logger.setLevel(logging.INFO)
        rfh.setLevel(logging.INFO)
        self.publisher_logger.addHandler(rfh)

    def publish_samples(self, samples):
        """Send a metering message for publishing

        :param samples: Samples from pipeline after transformation
        """
        if self.publisher_logger:
            for sample in samples:
                self.publisher_logger.info(sample.as_dict())

    def publish_events(self, events):
        """Send an event message for publishing

        :param events: events from pipeline after transformation
        """
        if self.publisher_logger:
            for event in events:
                self.publisher_logger.info(event.as_dict())
