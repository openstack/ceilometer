# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Base class for plugins.
"""

import abc
from collections import namedtuple

from ceilometer.openstack.common import cfg
# Import rabbit_notifier to register notification_topics flag so that
# plugins can use it
import ceilometer.openstack.common.notifier.rabbit_notifier


ExchangeTopics = namedtuple('ExchangeTopics', ['exchange', 'topics'])


class NotificationBase(object):
    """Base class for plugins that support the notification API."""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_event_types(self):
        """Return a sequence of strings defining the event types to be
        given to this plugin."""

    @abc.abstractmethod
    def get_exchange_topics(self, conf):
        """Return a sequence of ExchangeTopics defining the exchange and
        topics to be connected for this plugin."""

    @abc.abstractmethod
    def process_notification(self, message):
        """Return a sequence of Counter instances for the given message."""

    def notification_to_metadata(self, event):
        """Transform a payload dict to a metadata dict."""
        metadata = dict([(k, event['payload'].get(k))
                         for k in self.metadata_keys])
        metadata['event_type'] = event['event_type']
        metadata['host'] = event['publisher_id']
        return metadata


class PollsterBase(object):
    """Base class for plugins that support the polling API."""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_counters(self, manager, instance):
        """Return a sequence of Counter instances from polling the
        resources."""
