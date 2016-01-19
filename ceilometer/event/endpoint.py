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
from ceilometer.i18n import _LE
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

    def info(self, notifications):
        """Convert message at info level to Ceilometer Event.

        :param notifications: list of notifications
        """
        return self.process_notification('info', notifications)

    def error(self, notifications):
        """Convert message at error level to Ceilometer Event.

        :param notifications: list of notifications
        """
        return self.process_notification('error', notifications)

    def process_notification(self, priority, notifications):
        for notification in notifications:
            # NOTE: the rpc layer currently rips out the notification
            # delivery_info, which is critical to determining the
            # source of the notification. This will have to get added back
            # later.
            notification = messaging.convert_to_old_notification_format(
                priority, notification)
            try:
                event = self.event_converter.to_event(notification)
                if event is not None:
                    with self.manager.publisher(self.ctxt) as p:
                        p(event)
            except Exception:
                if not cfg.CONF.notification.ack_on_event_error:
                    return oslo_messaging.NotificationResult.REQUEUE
                LOG.error(_LE('Fail to process a notification'), exc_info=True)
        return oslo_messaging.NotificationResult.HANDLED
