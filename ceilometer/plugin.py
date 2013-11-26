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
import collections
import fnmatch

from oslo.config import cfg
import six

# Import this option so every Notification plugin can use it freely.
cfg.CONF.import_opt('notification_topics',
                    'ceilometer.openstack.common.notifier.rpc_notifier')


ExchangeTopics = collections.namedtuple('ExchangeTopics',
                                        ['exchange', 'topics'])


class PluginBase(object):
    """Base class for all plugins.
    """


@six.add_metaclass(abc.ABCMeta)
class NotificationBase(PluginBase):
    """Base class for plugins that support the notification API."""

    @abc.abstractproperty
    def event_types(self):
        """Return a sequence of strings defining the event types to be
        given to this plugin.
        """

    @abc.abstractmethod
    def get_exchange_topics(self, conf):
        """Return a sequence of ExchangeTopics defining the exchange and
        topics to be connected for this plugin.

        :param conf: Configuration.
        """

    @abc.abstractmethod
    def process_notification(self, message):
        """Return a sequence of Counter instances for the given message.

        :param message: Message to process.
        """

    @staticmethod
    def _handle_event_type(event_type, event_type_to_handle):
        """Check whether event_type should be handled according to
        event_type_to_handle.

        """
        return any(map(lambda e: fnmatch.fnmatch(event_type, e),
                       event_type_to_handle))

    def to_samples(self, notification):
        """Return samples produced by *process_notification* for the given
        notification, if it's handled by this notification handler.

        :param notification: The notification to process.

        """
        if self._handle_event_type(notification['event_type'],
                                   self.event_types):
            return self.process_notification(notification)
        return []


@six.add_metaclass(abc.ABCMeta)
class PollsterBase(PluginBase):
    """Base class for plugins that support the polling API."""

    @abc.abstractmethod
    def get_samples(self, manager, cache, resources=[]):
        """Return a sequence of Counter instances from polling the resources.

        :param manager: The service manager class invoking the plugin.
        :param cache: A dictionary to allow pollsters to pass data
                      between themselves when recomputing it would be
                      expensive (e.g., asking another service for a
                      list of objects).
        :param resources: A list of the endpoints the pollster will get data
                          from. It's up to the specific pollster to decide
                          how to use it.

        """
