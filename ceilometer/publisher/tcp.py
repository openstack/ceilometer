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
        self.host, self.port = netutils.parse_host_port(
            parsed_url.netloc, default_port=4952)
        addrinfo = None
        try:
            addrinfo = socket.getaddrinfo(self.host, None, socket.AF_INET6,
                                          socket.SOCK_STREAM)[0]
        except socket.gaierror:
            try:
                addrinfo = socket.getaddrinfo(self.host, None, socket.AF_INET,
                                              socket.SOCK_STREAM)[0]
            except socket.gaierror:
                pass
        if addrinfo:
            self.addr_family = addrinfo[0]
        else:
            LOG.warning(
                "Cannot resolve host %s, creating AF_INET socket...",
                self.host)
            self.addr_family = socket.AF_INET
        try:
            self.create_and_connect()
        except Exception:
            LOG.error(_("Unable to connect to the "
                      "remote endpoint"))

    def create_and_connect(self):
        self.socket = socket.socket(self.addr_family,
                                    socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

    def publish_samples(self, samples):
        """Send a metering message for publishing

        :param samples: Samples from pipeline after transformation
        """

        for sample in samples:
            msg = utils.meter_message_from_counter(
                sample, self.conf.publisher.telemetry_secret, self.conf.host)
            host = self.host
            port = self.port
            LOG.debug("Publishing sample %(msg)s over TCP to "
                      "%(host)s:%(port)d", {'msg': msg, 'host': host,
                                            'port': port})
            encoded_msg = msgpack.dumps(msg, use_bin_type=True)
            msg_len = len(encoded_msg).to_bytes(8, 'little')
            try:
                self.socket.send(msg_len + encoded_msg)
            except Exception:
                LOG.error(_("Unable to send sample over TCP,"
                          "trying to reconnect and resend the message"))
                self.create_and_connect()
                try:
                    self.socket.send(msg_len + encoded_msg)
                except Exception:
                    LOG.exception(_("Unable to reconnect and resend"
                                  "sample over TCP"))

    def publish_events(self, events):
        """Send an event message for publishing

        :param events: events from pipeline after transformation
        """
        raise ceilometer.NotImplementedError
