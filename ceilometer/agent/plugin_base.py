#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

from keystoneclient.v2_0 import client as ksclient
import oslo.messaging
from oslo_config import cfg
from oslo_context import context
import six

from ceilometer.i18n import _
from ceilometer import messaging
from ceilometer.openstack.common import log
from ceilometer.publisher import utils

cfg.CONF.import_group('service_credentials', 'ceilometer.service')

LOG = log.getLogger(__name__)

ExchangeTopics = collections.namedtuple('ExchangeTopics',
                                        ['exchange', 'topics'])


def _get_keystone():
    try:
        return ksclient.Client(
            username=cfg.CONF.service_credentials.os_username,
            password=cfg.CONF.service_credentials.os_password,
            tenant_id=cfg.CONF.service_credentials.os_tenant_id,
            tenant_name=cfg.CONF.service_credentials.os_tenant_name,
            cacert=cfg.CONF.service_credentials.os_cacert,
            auth_url=cfg.CONF.service_credentials.os_auth_url,
            region_name=cfg.CONF.service_credentials.os_region_name,
            insecure=cfg.CONF.service_credentials.insecure)
    except Exception as e:
        return e


def check_keystone(service_type=None):
    """Decorator function to check if manager has valid keystone client.

       Also checks if the service is registered/enabled in Keystone.

       :param service_type: name of service in Keystone
    """
    def wrapped(f):
        def func(self, *args, **kwargs):
            manager = kwargs.get('manager')
            if not manager and len(args) > 0:
                manager = args[0]
            keystone = getattr(manager, 'keystone', None)
            if not keystone:
                keystone = _get_keystone()
            if isinstance(keystone, Exception):
                LOG.error(_('Skip due to keystone error %s'),
                          keystone if keystone else '')
                return iter([])
            elif service_type:
                endpoints = keystone.service_catalog.get_endpoints(
                    service_type=service_type)
                if not endpoints:
                    LOG.warning(_('Skipping because %s service is not '
                                  'registered in keystone') % service_type)
                    return iter([])
            return f(self, *args, **kwargs)
        return func
    return wrapped


class PluginBase(object):
    """Base class for all plugins."""


@six.add_metaclass(abc.ABCMeta)
class NotificationBase(PluginBase):
    """Base class for plugins that support the notification API."""
    def __init__(self, transporter):
        super(NotificationBase, self).__init__()
        self.transporter = transporter
        # NOTE(gordc): if no publisher, this isn't a PipelineManager and
        # data should be requeued.
        self.requeue = False if hasattr(transporter, 'publisher') else True

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

        # TODO(sileht): Backwards compatibility, remove in J+2
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

        if self.requeue:
            meters = [
                utils.meter_message_from_counter(
                    sample, cfg.CONF.publisher.telemetry_secret)
                for sample in self.process_notification(notification)
            ]
            for notifier in self.transporter:
                notifier.sample(context.to_dict(),
                                event_type='ceilometer.pipeline',
                                payload=meters)
        else:
            with self.transporter.publisher(context) as p:
                p(list(self.process_notification(notification)))


class ExtensionLoadError(Exception):
    """Error of loading pollster plugin.

    PollsterBase provides a hook, setup_environment, called in pollster loading
    to setup required HW/SW dependency. Any exception from it would be
    propagated as ExtensionLoadError, then skip loading this pollster.
    """
    pass


class PollsterPermanentError(Exception):
    """Permenant error when polling.

    When unrecoverable error happened in polling, pollster can raise this
    exception with failed resource to prevent itself from polling any more.
    Resource is one of parameter resources from get_samples that cause polling
    error.
    """

    def __init__(self, resource):
        self.fail_res = resource


@six.add_metaclass(abc.ABCMeta)
class PollsterBase(PluginBase):
    """Base class for plugins that support the polling API."""

    def setup_environment(self):
        """Setup required environment for pollster.

        Each subclass could overwrite it for specific usage. Any exception
        raised in this function would prevent pollster being loaded.
        """
        pass

    def __init__(self):
        super(PollsterBase, self).__init__()
        try:
            self.setup_environment()
        except Exception as err:
            raise ExtensionLoadError(err)

    @abc.abstractproperty
    def default_discovery(self):
        """Default discovery to use for this pollster.

        There are three ways a pollster can get a list of resources to poll,
        listed here in ascending order of precedence:
        1. from the per-agent discovery,
        2. from the per-pollster discovery (defined here)
        3. from the per-pipeline configured discovery and/or per-pipeline
        configured static resources.

        If a pollster should only get resources from #1 or #3, this property
        should be set to None.
        """

    @abc.abstractmethod
    def get_samples(self, manager, cache, resources):
        """Return a sequence of Counter instances from polling the resources.

        :param manager: The service manager class invoking the plugin.
        :param cache: A dictionary to allow pollsters to pass data
                      between themselves when recomputing it would be
                      expensive (e.g., asking another service for a
                      list of objects).
        :param resources: A list of resources the pollster will get data
                          from. It's up to the specific pollster to decide
                          how to use it. It is usually supplied by a discovery,
                          see ``default_discovery`` for more information.

        """


@six.add_metaclass(abc.ABCMeta)
class DiscoveryBase(object):
    @abc.abstractmethod
    def discover(self, manager, param=None):
        """Discover resources to monitor.

        The most fine-grained discovery should be preferred, so the work is
        the most evenly distributed among multiple agents (if they exist).

        For example:
        if the pollster can separately poll individual resources, it should
        have its own discovery implementation to discover those resources. If
        it can only poll per-tenant, then the `TenantDiscovery` should be
        used. If even that is not possible, use `EndpointDiscovery` (see
        their respective docstrings).

        :param manager: The service manager class invoking the plugin.
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
