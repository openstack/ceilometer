# -*- encoding: utf-8 -*-
#
# Copyright © 2012-2014 eNovance <licensing@enovance.com>
#
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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

from oslo.config import cfg
import oslo.messaging
from stevedore import extension

from ceilometer.event import converter as event_converter
from ceilometer import messaging
from ceilometer.openstack.common.gettextutils import _
from ceilometer import service
from ceilometer.storage import models

LOG = logging.getLogger(__name__)


class EventsNotificationEndpoint(service.DispatchedService):
    def __init__(self):
        LOG.debug(_('Loading event definitions'))
        self.event_converter = event_converter.setup_events(
            extension.ExtensionManager(
                namespace='ceilometer.event.trait_plugin'))

    def info(self, ctxt, publisher_id, event_type, payload, metadata):
        """Convert message to Ceilometer Event.

        :param ctxt: oslo.messaging context
        :param publisher_id: publisher of the notification
        :param event_type: type of notification
        :param payload: notification payload
        :param metadata: metadata about the notification
        """

        #NOTE: the rpc layer currently rips out the notification
        #delivery_info, which is critical to determining the
        #source of the notification. This will have to get added back later.
        notification = messaging.convert_to_old_notification_format(
            'info', ctxt, publisher_id, event_type, payload, metadata)
        self.process_notification(notification)

    def process_notification(self, notification):
        event = self.event_converter.to_event(notification)

        if event is not None:
            LOG.debug(_('Saving event "%s"'), event.event_type)
            problem_events = []
            for dispatcher in self.dispatcher_manager:
                problem_events.extend(dispatcher.obj.record_events(event))
            if models.Event.UNKNOWN_PROBLEM in [x[0] for x in problem_events]:
                if not cfg.CONF.notification.ack_on_event_error:
                    return oslo.messaging.NotificationResult.REQUEUE
        return oslo.messaging.NotificationResult.HANDLED
