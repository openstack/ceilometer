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

# Import rpc_notifier to register notification_topics flag so that
# plugins can use it
import ceilometer.openstack.common.notifier.rpc_notifier


ExchangeTopics = namedtuple('ExchangeTopics', ['exchange', 'topics'])


class PluginBase(object):
    """Base class for all plugins.
    """

    def is_enabled(self):
        """Return boolean indicating whether this plugin should
        be enabled and used by the caller.
        """
        return True


class NotificationBase(PluginBase):
    """Base class for plugins that support the notification API."""

    __metaclass__ = abc.ABCMeta

    def is_enabled(self):
        return True

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


class PollsterBase(PluginBase):
    """Base class for plugins that support the polling API."""

    __metaclass__ = abc.ABCMeta

    @staticmethod
    @abc.abstractmethod
    def get_counter_names():
        """Return a sequence of Counter names supported by the pollster."""

    @abc.abstractmethod
    def get_counters(self, manager, instance):
        """Return a sequence of Counter instances from polling the
        resources."""


class PublisherBase(PluginBase):
    """Base class for plugins that publish the sampler."""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def publish_counters(self, context, counters, source):
        "Publish counters into final conduit"


class TransformerBase(PluginBase):
    """Base class for plugins that transform the counter."""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def handle_sample(self, context, counter, source):
        """Transform a counter

        parameter:
            context: Passed from the data collector
            counters: An interator of counters.
            source: Passed from data collector.

        """

    def flush(self, context, source):
        """Flush counters cached previously"""
        return []

    def __init__(self, **parameter):
        """Setup transformer

        Each time a transformed is involved in a pipeline, a new transformer
        instance is created and chained into the pipeline. i.e. transformer
        instance is per pipeline. This helps if transformer need keep some
        cache and per-pipeline information.

        parameter:
            kwds: the parameter that is defined in pipeline config file

        """
        super(TransformerBase, self).__init__()
