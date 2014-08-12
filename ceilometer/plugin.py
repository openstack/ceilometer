#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

import oslo.messaging
import six

from ceilometer import messaging
from ceilometer.openstack.common import context
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)

ExchangeTopics = collections.namedtuple('ExchangeTopics',
                                        ['exchange', 'topics'])


class PluginBase(object):
    """Base class for all plugins."""


@six.add_metaclass(abc.ABCMeta)
class NotificationBase(PluginBase):
    """Base class for plugins that support the notification API."""
    def __init__(self, pipeline_manager):
        super(NotificationBase, self).__init__()
        self.pipeline_manager = pipeline_manager

    @abc.abstractproperty
    def event_types(self):
        """Return a sequence of strings.

        Strings are defining the event types to be given to this plugin.
        """

    def get_targets(self, conf):
        """Return a sequence of oslo.messaging.Target.

        Sequence is defining the exchange and topics to be connected for this
        plugin.
        :param conf: Configuration.
        """

        # TODO(sileht): Backwards compatibility, remove in J+1
        if hasattr(self, 'get_exchange_topics'):
            LOG.warn(_('get_exchange_topics API of NotificationPlugin is'
                       'deprecated, implements get_targets instead.'))

            targets = []
            for exchange, topics in self.get_exchange_topics(conf):
                targets.extend(oslo.messaging.Target(topic=topic,
                                                     exchange=exchange)
                               for topic in topics)
            return targets

    @abc.abstractmethod
    def process_notification(self, message):
        """Return a sequence of Counter instances for the given message.

        :param message: Message to process.
        """

    @staticmethod
    def _handle_event_type(event_type, event_type_to_handle):
        """Check whether event_type should be handled.

        It is according to event_type_to_handle.
        """
        return any(map(lambda e: fnmatch.fnmatch(event_type, e),
                       event_type_to_handle))

    def info(self, ctxt, publisher_id, event_type, payload, metadata):
        """RPC endpoint for notification messages

        When another service sends a notification over the message
        bus, this method receives it.

        :param ctxt: oslo.messaging context
        :param publisher_id: publisher of the notification
        :param event_type: type of notification
        :param payload: notification payload
        :param metadata: metadata about the notification

        """
        notification = messaging.convert_to_old_notification_format(
            'info', ctxt, publisher_id, event_type, payload, metadata)
        self.to_samples_and_publish(context.get_admin_context(), notification)

    def to_samples_and_publish(self, context, notification):
        """Return samples produced by *process_notification*.

        Samples produced for the given notification.
        :param context: Execution context from the service or RPC call
        :param notification: The notification to process.
        """

        # TODO(sileht): this will be moved into oslo.messaging
        # see oslo.messaging bp notification-dispatcher-filter
        if not self._handle_event_type(notification['event_type'],
                                       self.event_types):
            return

        with self.pipeline_manager.publisher(context) as p:
            p(list(self.process_notification(notification)))


@six.add_metaclass(abc.ABCMeta)
class PollsterBase(PluginBase):
    """Base class for plugins that support the polling API."""

    @abc.abstractmethod
    def get_samples(self, manager, cache, resources=None):
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


@six.add_metaclass(abc.ABCMeta)
class DiscoveryBase(object):
    @abc.abstractmethod
    def discover(self, param=None):
        """Discover resources to monitor.

        :param param: an optional parameter to guide the discovery
        """

    @property
    def group_id(self):
        """Return group id of this discovery.

        All running recoveries with the same group_id should return the same
        set of resources at a given point in time. By default, a discovery is
        put into a global group, meaning that all discoveries of its type
        running anywhere in the cloud, return the same set of resources.

        This property can be overridden to provide correct grouping of
        localized discoveries. For example, compute discovery is localized
        to a host, which is reflected in its group_id.

        A None value signifies that this discovery does not want to be part
        of workload partitioning at all.
        """
        return 'global'
