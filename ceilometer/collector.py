#
# Copyright 2012-2013 eNovance <licensing@enovance.com>
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

from itertools import chain
import socket

import msgpack
from oslo_config import cfg
from oslo_log import log
import oslo_messaging
from oslo_service import service as os_service
from oslo_utils import netutils
from oslo_utils import units

from ceilometer import dispatcher
from ceilometer.i18n import _, _LE
from ceilometer import messaging
from ceilometer import utils

OPTS = [
    cfg.StrOpt('udp_address',
               default='0.0.0.0',
               help='Address to which the UDP socket is bound. Set to '
               'an empty string to disable.'),
    cfg.PortOpt('udp_port',
                default=4952,
                help='Port to which the UDP socket is bound.'),
    cfg.BoolOpt('requeue_sample_on_dispatcher_error',
                default=False,
                help='Requeue the sample on the collector sample queue '
                'when the collector fails to dispatch it. This is only valid '
                'if the sample come from the notifier publisher.'),
    cfg.BoolOpt('requeue_event_on_dispatcher_error',
                default=False,
                help='Requeue the event on the collector event queue '
                'when the collector fails to dispatch it.'),
    cfg.IntOpt('batch_size',
               default=1,
               help='Number of notification messages to wait before '
               'dispatching them'),
    cfg.IntOpt('batch_timeout',
               default=None,
               help='Number of seconds to wait before dispatching samples'
               'when batch_size is not reached (None means indefinitely)'),
]

cfg.CONF.register_opts(OPTS, group="collector")
cfg.CONF.import_opt('metering_topic', 'ceilometer.publisher.messaging',
                    group='publisher_notifier')
cfg.CONF.import_opt('event_topic', 'ceilometer.publisher.messaging',
                    group='publisher_notifier')
cfg.CONF.import_opt('store_events', 'ceilometer.notification',
                    group='notification')


LOG = log.getLogger(__name__)


class CollectorService(os_service.Service):
    """Listener for the collector service."""
    def start(self):
        """Bind the UDP socket and handle incoming data."""
        # ensure dispatcher is configured before starting other services
        dispatcher_managers = dispatcher.load_dispatcher_manager()
        (self.meter_manager, self.event_manager) = dispatcher_managers
        self.sample_listener = None
        self.event_listener = None
        super(CollectorService, self).start()

        if cfg.CONF.collector.udp_address:
            self.tg.add_thread(self.start_udp)

        transport = messaging.get_transport(optional=True)
        if transport:
            if list(self.meter_manager):
                sample_target = oslo_messaging.Target(
                    topic=cfg.CONF.publisher_notifier.metering_topic)
                self.sample_listener = (
                    messaging.get_batch_notification_listener(
                        transport, [sample_target],
                        [SampleEndpoint(self.meter_manager)],
                        allow_requeue=(cfg.CONF.collector.
                                       requeue_sample_on_dispatcher_error),
                        batch_size=cfg.CONF.collector.batch_size,
                        batch_timeout=cfg.CONF.collector.batch_timeout))
                self.sample_listener.start()

            if cfg.CONF.notification.store_events and list(self.event_manager):
                event_target = oslo_messaging.Target(
                    topic=cfg.CONF.publisher_notifier.event_topic)
                self.event_listener = (
                    messaging.get_batch_notification_listener(
                        transport, [event_target],
                        [EventEndpoint(self.event_manager)],
                        allow_requeue=(cfg.CONF.collector.
                                       requeue_event_on_dispatcher_error),
                        batch_size=cfg.CONF.collector.batch_size,
                        batch_timeout=cfg.CONF.collector.batch_timeout))
                self.event_listener.start()

            if not cfg.CONF.collector.udp_address:
                # Add a dummy thread to have wait() working
                self.tg.add_timer(604800, lambda: None)

    def start_udp(self):
        address_family = socket.AF_INET
        if netutils.is_valid_ipv6(cfg.CONF.collector.udp_address):
            address_family = socket.AF_INET6
        udp = socket.socket(address_family, socket.SOCK_DGRAM)
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
                LOG.warning(_("UDP: Cannot decode data sent by %s"), source)
            else:
                try:
                    LOG.debug("UDP: Storing %s", sample)
                    self.meter_manager.map_method('record_metering_data',
                                                  sample)
                except Exception:
                    LOG.exception(_("UDP: Unable to store meter"))

    def stop(self):
        self.udp_run = False
        if self.sample_listener:
            utils.kill_listeners([self.sample_listener])
        if self.event_listener:
            utils.kill_listeners([self.event_listener])
        super(CollectorService, self).stop()

    def record_metering_data(self, context, data):
        """RPC endpoint for messages we send to ourselves.

        When the notification messages are re-published through the
        RPC publisher, this method receives them for processing.
        """
        self.meter_manager.map_method('record_metering_data', data=data)


class CollectorEndpoint(object):
    def __init__(self, dispatcher_manager, requeue_on_error):
        self.dispatcher_manager = dispatcher_manager
        self.requeue_on_error = requeue_on_error

    def sample(self, messages):
        """RPC endpoint for notification messages

        When another service sends a notification over the message
        bus, this method receives it.
        """
        samples = list(chain.from_iterable(m["payload"] for m in messages))
        try:
            self.dispatcher_manager.map_method(self.method, samples)
        except Exception:
            if self.requeue_on_error:
                LOG.exception(_LE("Dispatcher failed to handle the %s, "
                                  "requeue it."), self.ep_type)
                return oslo_messaging.NotificationResult.REQUEUE
            raise


class SampleEndpoint(CollectorEndpoint):
    method = 'record_metering_data'
    ep_type = 'sample'

    def __init__(self, dispatcher_manager):
        super(SampleEndpoint, self).__init__(
            dispatcher_manager,
            cfg.CONF.collector.requeue_sample_on_dispatcher_error)


class EventEndpoint(CollectorEndpoint):
    method = 'record_events'
    ep_type = 'event'

    def __init__(self, dispatcher_manager):
        super(EventEndpoint, self).__init__(
            dispatcher_manager,
            cfg.CONF.collector.requeue_event_on_dispatcher_error)
