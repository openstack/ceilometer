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

from oslo.config import cfg
from stevedore import extension

from ceilometer.event import endpoint as event_endpoint
from ceilometer import messaging
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer.openstack.common import service as os_service
from ceilometer import pipeline


LOG = log.getLogger(__name__)


OPTS = [
    cfg.BoolOpt('ack_on_event_error',
                default=True,
                deprecated_group='collector',
                help='Acknowledge message when event persistence fails.'),
    cfg.BoolOpt('store_events',
                deprecated_group='collector',
                default=False,
                help='Save event details.'),
    cfg.MultiStrOpt('messaging_urls',
                    default=[],
                    help="Messaging URLs to listen for notifications. "
                         "Example: transport://user:pass@host1:port"
                         "[,hostN:portN]/virtual_host "
                         "(DEFAULT/transport_url is used if empty)"),
]

cfg.CONF.register_opts(OPTS, group="notification")


class NotificationService(os_service.Service):

    NOTIFICATION_NAMESPACE = 'ceilometer.notification'

    @classmethod
    def _get_notifications_manager(cls, pm):
        return extension.ExtensionManager(
            namespace=cls.NOTIFICATION_NAMESPACE,
            invoke_on_load=True,
            invoke_args=(pm, )
        )

    def start(self):
        super(NotificationService, self).start()
        # FIXME(sileht): endpoint use notification_topics option
        # and it should not because this is oslo.messaging option
        # not a ceilometer, until we have a something to get
        # the notification_topics in an other way
        # we must create a transport to ensure the option have
        # beeen registered by oslo.messaging
        transport = messaging.get_transport()
        messaging.get_notifier(transport, '')

        self.pipeline_manager = pipeline.setup_pipeline()

        self.notification_manager = self._get_notifications_manager(
            self.pipeline_manager)
        if not list(self.notification_manager):
            LOG.warning(_('Failed to load any notification handlers for %s'),
                        self.NOTIFICATION_NAMESPACE)

        ack_on_error = cfg.CONF.notification.ack_on_event_error

        endpoints = []
        if cfg.CONF.notification.store_events:
            endpoints = [event_endpoint.EventsNotificationEndpoint()]

        targets = []
        for ext in self.notification_manager:
            handler = ext.obj
            LOG.debug(_('Event types from %(name)s: %(type)s'
                        ' (ack_on_error=%(error)s)') %
                      {'name': ext.name,
                       'type': ', '.join(handler.event_types),
                       'error': ack_on_error})
            targets.extend(handler.get_targets(cfg.CONF))
            endpoints.append(handler)

        urls = cfg.CONF.notification.messaging_urls or [None]
        self.listeners = []
        for url in urls:
            transport = messaging.get_transport(url)
            listener = messaging.get_notification_listener(
                transport, targets, endpoints)
            listener.start()
            self.listeners.append(listener)

        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def stop(self):
        map(lambda x: x.stop(), self.listeners)
        super(NotificationService, self).stop()
