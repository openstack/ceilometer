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
import select
import socket

import cotyledon
import msgpack
from oslo_config import cfg
from oslo_log import log
import oslo_messaging
from oslo_utils import netutils
from oslo_utils import units

from ceilometer import dispatcher
from ceilometer.i18n import _
from ceilometer import messaging
from ceilometer.publisher import utils as publisher_utils
from ceilometer import utils

OPTS = [
    cfg.HostAddressOpt('udp_address',
                       default='0.0.0.0',
                       help='Address to which the UDP socket is bound. Set to '
                       'an empty string to disable.'),
    cfg.PortOpt('udp_port',
                default=4952,
                help='Port to which the UDP socket is bound.'),
    cfg.IntOpt('batch_size',
               default=1,
               help='Number of notification messages to wait before '
               'dispatching them'),
    cfg.IntOpt('batch_timeout',
               help='Number of seconds to wait before dispatching samples '
               'when batch_size is not reached (None means indefinitely)'),
    cfg.IntOpt('workers',
               default=1,
               min=1,
               deprecated_group='DEFAULT',
               deprecated_name='collector_workers',
               help='Number of workers for collector service. '
               'default value is 1.')
]

LOG = log.getLogger(__name__)


class CollectorService(cotyledon.Service):
    """Listener for the collector service."""
    def __init__(self, worker_id, conf):
        super(CollectorService, self).__init__(worker_id)
        self.conf = conf
        # ensure dispatcher is configured before starting other services
        dispatcher_managers = dispatcher.load_dispatcher_manager(conf)
        (self.meter_manager, self.event_manager) = dispatcher_managers
        self.sample_listener = None
        self.event_listener = None
        self.udp_thread = None

        import debtcollector
        debtcollector.deprecate("Ceilometer collector service is deprecated."
                                "Use publishers to push data instead",
                                version="9.0", removal_version="10.0")

    def run(self):
        if self.conf.collector.udp_address:
            self.udp_thread = utils.spawn_thread(self.start_udp)

        transport = messaging.get_transport(self.conf, optional=True)
        if transport:
            if list(self.meter_manager):
                sample_target = oslo_messaging.Target(
                    topic=self.conf.publisher_notifier.metering_topic)
                self.sample_listener = (
                    messaging.get_batch_notification_listener(
                        transport, [sample_target],
                        [SampleEndpoint(self.conf.publisher.telemetry_secret,
                                        self.meter_manager)],
                        allow_requeue=True,
                        batch_size=self.conf.collector.batch_size,
                        batch_timeout=self.conf.collector.batch_timeout))
                self.sample_listener.start()

            if list(self.event_manager):
                event_target = oslo_messaging.Target(
                    topic=self.conf.publisher_notifier.event_topic)
                self.event_listener = (
                    messaging.get_batch_notification_listener(
                        transport, [event_target],
                        [EventEndpoint(self.conf.publisher.telemetry_secret,
                                       self.event_manager)],
                        allow_requeue=True,
                        batch_size=self.conf.collector.batch_size,
                        batch_timeout=self.conf.collector.batch_timeout))
                self.event_listener.start()

    def start_udp(self):
        address_family = socket.AF_INET
        if netutils.is_valid_ipv6(self.conf.collector.udp_address):
            address_family = socket.AF_INET6
        udp = socket.socket(address_family, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            # NOTE(zhengwei): linux kernel >= 3.9
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except Exception:
            LOG.warning("System does not support socket.SO_REUSEPORT "
                        "option. Only one worker will be able to process "
                        "incoming data.")
        udp.bind((self.conf.collector.udp_address,
                  self.conf.collector.udp_port))

        self.udp_run = True
        while self.udp_run:
            # NOTE(sileht): return every 10 seconds to allow
            # clear shutdown
            if not select.select([udp], [], [], 10.0)[0]:
                continue
            # NOTE(jd) Arbitrary limit of 64K because that ought to be
            # enough for anybody.
            data, source = udp.recvfrom(64 * units.Ki)
            try:
                sample = msgpack.loads(data, encoding='utf-8')
            except Exception:
                LOG.warning(_("UDP: Cannot decode data sent by %s"), source)
            else:
                if publisher_utils.verify_signature(
                        sample, self.conf.publisher.telemetry_secret):
                    try:
                        LOG.debug("UDP: Storing %s", sample)
                        self.meter_manager.map_method(
                            'record_metering_data', sample)
                    except Exception:
                        LOG.exception(_("UDP: Unable to store meter"))
                else:
                    LOG.warning('sample signature invalid, '
                                'discarding: %s', sample)

    def terminate(self):
        if self.sample_listener:
            utils.kill_listeners([self.sample_listener])
        if self.event_listener:
            utils.kill_listeners([self.event_listener])
        if self.udp_thread:
            self.udp_run = False
            self.udp_thread.join()
        super(CollectorService, self).terminate()


class CollectorEndpoint(object):
    def __init__(self, secret, dispatcher_manager):
        self.secret = secret
        self.dispatcher_manager = dispatcher_manager

    def sample(self, messages):
        """RPC endpoint for notification messages

        When another service sends a notification over the message
        bus, this method receives it.
        """
        goods = []
        for sample in chain.from_iterable(m["payload"] for m in messages):
            if publisher_utils.verify_signature(sample, self.secret):
                goods.append(sample)
            else:
                LOG.warning('notification signature invalid, '
                            'discarding: %s', sample)
        try:
            self.dispatcher_manager.map_method(self.method, goods)
        except Exception:
            LOG.exception("Dispatcher failed to handle the notification, "
                          "re-queuing it.")
            return oslo_messaging.NotificationResult.REQUEUE


class SampleEndpoint(CollectorEndpoint):
    method = 'record_metering_data'


class EventEndpoint(CollectorEndpoint):
    method = 'record_events'
