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
"""Publish a counter using an UDP mechanism
"""

from ceilometer import publisher
from ceilometer.openstack.common import log
from ceilometer.openstack.common.gettextutils import _
from oslo.config import cfg
import msgpack
import socket

LOG = log.getLogger(__name__)

UDP_PUBLISH_GROUP = cfg.OptGroup(name='publisher_udp',
                                 title='Options for UDP publisher')

UDP_PUBLISH_OPTS = [
    cfg.StrOpt('host',
               default="localhost",
               help='The host target to publish metering records to.',
               ),
    cfg.IntOpt('port',
               default=4952,
               help='The port to send UDP meters to.',
               ),
]


def register_opts(config):
    """Register the options for publishing UDP messages.
    """
    config.register_group(UDP_PUBLISH_GROUP)
    config.register_opts(UDP_PUBLISH_OPTS,
                         group=UDP_PUBLISH_GROUP)


register_opts(cfg.CONF)


class UDPPublisher(publisher.PublisherBase):

    def __init__(self):
        self.socket = socket.socket(socket.AF_INET,
                                    socket.SOCK_DGRAM)

    def publish_counters(self, context, counters, source):
        """Send a metering message for publishing

        :param context: Execution context from the service or RPC call
        :param counter: Counter from pipeline after transformation
        :param source: counter source
        """

        for counter in counters:
            msg = counter._asdict()
            msg['source'] = source
            host = cfg.CONF.publisher_udp.host
            port = cfg.CONF.publisher_udp.port
            LOG.debug(_("Publishing counter %(msg)s over "
                        "UDP to %(host)s:%(port)d") % locals())
            try:
                self.socket.sendto(msgpack.dumps(msg),
                                   (cfg.CONF.publisher_udp.host,
                                    cfg.CONF.publisher_udp.port))
            except Exception as e:
                LOG.warn(_("Unable to send counter over UDP"))
                LOG.exception(e)
