# Copyright 2012-2014 eNovance <licensing@enovance.com>
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

from oslo_config import cfg
from oslo_context import context
import oslo_messaging
from stevedore import extension

from ceilometer.event import converter as event_converter
from ceilometer import messaging

LOG = logging.getLogger(__name__)


class EventsNotificationEndpoint(object):
    def __init__(self, manager):
        super(EventsNotificationEndpoint, self).__init__()
        LOG.debug('Loading event definitions')
        self.ctxt = context.get_admin_context()
        self.event_converter = event_converter.setup_events(
            extension.ExtensionManager(
                namespace='ceilometer.event.trait_plugin'))
        self.manager = manager

    def info(self, ctxt, publisher_id, event_type, payload, metadata):
        """Convert message at info level to Ceilometer Event.

        :param ctxt: oslo_messaging context
        :param publisher_id: publisher of the notification
        :param event_type: type of notification
        :param payload: notification payload
        :param metadata: metadata about the notification
        """

        # NOTE: the rpc layer currently rips out the notification
        # delivery_info, which is critical to determining the
        # source of the notification. This will have to get added back later.
        notification = messaging.convert_to_old_notification_format(
            'info', ctxt, publisher_id, event_type, payload, metadata)
        return self.process_notification(notification)

    def error(self, ctxt, publisher_id, event_type, payload, metadata):
        """Convert error message to Ceilometer Event.

        :param ctxt: oslo_messaging context
        :param publisher_id: publisher of the notification
        :param event_type: type of notification
        :param payload: notification payload
        :param metadata: metadata about the notification
        """

        # NOTE: the rpc layer currently rips out the notification
        # delivery_info, which is critical to determining the
        # source of the notification. This will have to get added back later.
        notification = messaging.convert_to_old_notification_format(
            'error', ctxt, publisher_id, event_type, payload, metadata)
        return self.process_notification(notification)

    def process_notification(self, notification):
        try:
            event = self.event_converter.to_event(notification)
            if event is not None:
                with self.manager.publisher(self.ctxt) as p:
                    p(event)
        except Exception:
            if not cfg.CONF.notification.ack_on_event_error:
                return oslo_messaging.NotificationResult.REQUEUE
            raise
        return oslo_messaging.NotificationResult.HANDLED
