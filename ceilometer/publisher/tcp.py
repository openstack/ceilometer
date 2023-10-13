#
# Copyright 2022 Red Hat, Inc
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
"""Publish a sample using a TCP mechanism
"""

import socket

import msgpack
from oslo_log import log
from oslo_utils import netutils

import ceilometer
from ceilometer.i18n import _
from ceilometer import publisher
from ceilometer.publisher import utils

LOG = log.getLogger(__name__)


class TCPPublisher(publisher.ConfigPublisherBase):
    def __init__(self, conf, parsed_url):
        super(TCPPublisher, self).__init__(conf, parsed_url)
        self.inet_addr = netutils.parse_host_port(
            parsed_url.netloc, default_port=4952)
        self.socket = None
        self.connect_socket()

    def connect_socket(self):
        try:
            self.socket = socket.create_connection(self.inet_addr)
            return True
        except socket.gaierror:
            LOG.error(_("Unable to resolv the remote %(host)s") %
                      {'host': self.inet_addr[0],
                       'port': self.inet_addr[1]})
        except TimeoutError:
            LOG.error(_("Unable to connect to the remote endpoint "
                        "%(host)s:%(port)d. The connection timed out.") %
                      {'host': self.inet_addr[0],
                       'port': self.inet_addr[1]})
        except ConnectionRefusedError:
            LOG.error(_("Unable to connect to the remote endpoint "
                        "%(host)s:%(port)d. Connection refused.") %
                      {'host': self.inet_addr[0],
                       'port': self.inet_addr[1]})
        return False

    def publish_samples(self, samples):
        """Send a metering message for publishing

        :param samples: Samples from pipeline after transformation
        """

        for sample in samples:
            msg = utils.meter_message_from_counter(
                sample, self.conf.publisher.telemetry_secret, self.conf.host)
            LOG.debug("Publishing sample %(msg)s over TCP to "
                      "%(host)s:%(port)d",
                      {'msg': msg,
                       'host': self.inet_addr[0],
                       'port': self.inet_addr[1]})
            encoded_msg = msgpack.dumps(msg, use_bin_type=True)
            msg_len = len(encoded_msg).to_bytes(8, 'little')
            if self.socket:
                try:
                    self.socket.send(msg_len + encoded_msg)
                    continue
                except OSError:
                    LOG.warning(_("Unable to send sample over TCP, trying "
                                  "to reconnect and resend the message"))
            if self.connect_socket():
                try:
                    self.socket.send(msg_len + encoded_msg)
                    continue
                except OSError:
                    pass
            LOG.error(_("Unable to reconnect and resend sample over TCP"))
            # NOTE (jokke): We do not handle exceptions in the calling code
            # so raising the exception from here needs quite a bit more work.
            # Same time we don't want to spam the retry messages as it's
            # unlikely to change between iterations on this loop. 'break'
            # rather than 'return' even the end result is the same feels
            # more appropriate for now.
            break

    def publish_events(self, events):
        """Send an event message for publishing

        :param events: events from pipeline after transformation
        """
        raise ceilometer.NotImplementedError
