#
# Copyright 2012-2013 eNovance <licensing@enovance.com>
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

import socket

import msgpack
from oslo.config import cfg
import oslo.messaging
from oslo.utils import units

from ceilometer import dispatcher
from ceilometer import messaging
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common.gettextutils import _LE
from ceilometer.openstack.common import log
from ceilometer.openstack.common import service as os_service

OPTS = [
    cfg.StrOpt('udp_address',
               default='0.0.0.0',
               help='Address to which the UDP socket is bound. Set to '
               'an empty string to disable.'),
    cfg.IntOpt('udp_port',
               default=4952,
               help='Port to which the UDP socket is bound.'),
    cfg.BoolOpt('requeue_sample_on_dispatcher_error',
                default=False,
                help='Requeue the sample on the collector sample queue '
                'when the collector fails to dispatch it. This is only valid '
                'if the sample come from the notifier publisher'),
]

cfg.CONF.register_opts(OPTS, group="collector")
cfg.CONF.import_opt('metering_topic', 'ceilometer.publisher.messaging',
                    group="publisher_rpc")
cfg.CONF.import_opt('metering_topic', 'ceilometer.publisher.messaging',
                    group="publisher_notifier")


LOG = log.getLogger(__name__)


class CollectorService(os_service.Service):
    """Listener for the collector service."""
    def start(self):
        """Bind the UDP socket and handle incoming data."""
        # ensure dispatcher is configured before starting other services
        self.dispatcher_manager = dispatcher.load_dispatcher_manager()
        self.rpc_server = None
        self.notification_server = None
        super(CollectorService, self).start()

        if cfg.CONF.collector.udp_address:
            self.tg.add_thread(self.start_udp)

        allow_requeue = cfg.CONF.collector.requeue_sample_on_dispatcher_error
        transport = messaging.get_transport(optional=True)
        if transport:
            self.rpc_server = messaging.get_rpc_server(
                transport, cfg.CONF.publisher_rpc.metering_topic, self)

            target = oslo.messaging.Target(
                topic=cfg.CONF.publisher_notifier.metering_topic)
            self.notification_server = messaging.get_notification_listener(
                transport, [target], [self],
                allow_requeue=allow_requeue)

            self.rpc_server.start()
            self.notification_server.start()

            if not cfg.CONF.collector.udp_address:
                # Add a dummy thread to have wait() working
                self.tg.add_timer(604800, lambda: None)

    def start_udp(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp.bind((cfg.CONF.collector.udp_address,
                  cfg.CONF.collector.udp_port))

        self.udp_run = True
        while self.udp_run:
            # NOTE(jd) Arbitrary limit of 64K because that ought to be
            # enough for anybody.
            data, source = udp.recvfrom(64 * units.Ki)
            try:
                sample = msgpack.loads(data, encoding='utf-8')
            except Exception:
                LOG.warn(_("UDP: Cannot decode data sent by %s"), str(source))
            else:
                try:
                    LOG.debug(_("UDP: Storing %s"), str(sample))
                    self.dispatcher_manager.map_method('record_metering_data',
                                                       sample)
                except Exception:
                    LOG.exception(_("UDP: Unable to store meter"))

    def stop(self):
        self.udp_run = False
        if self.rpc_server:
            self.rpc_server.stop()
        if self.notification_server:
            self.notification_server.stop()
        super(CollectorService, self).stop()

    def sample(self, ctxt, publisher_id, event_type, payload, metadata):
        """RPC endpoint for notification messages

        When another service sends a notification over the message
        bus, this method receives it.

        """
        try:
            self.dispatcher_manager.map_method('record_metering_data',
                                               data=payload)
        except Exception:
            if cfg.CONF.collector.requeue_sample_on_dispatcher_error:
                LOG.exception(_LE("Dispatcher failed to handle the sample, "
                                  "requeue it."))
                return oslo.messaging.NotificationResult.REQUEUE
            raise

    def record_metering_data(self, context, data):
        """RPC endpoint for messages we send to ourselves.

        When the notification messages are re-published through the
        RPC publisher, this method receives them for processing.
        """
        self.dispatcher_manager.map_method('record_metering_data', data=data)
