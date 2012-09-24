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
"""Given an incoming message, process it through the registered converters
and publish the results.
"""

import pkg_resources

from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)


class NotificationDispatcher(object):
    """Manages invoking plugins to convert notification messages to counters.
    """

    def __init__(self, plugin_namespace, publish_func):
        self.plugin_namespace = plugin_namespace
        self.publish_func = publish_func
        self.handlers = {}
        self.topics = set()
        self._load_plugins()

    def _load_plugins(self):
        # Listen for notifications from nova
        for ep in pkg_resources.iter_entry_points(self.plugin_namespace):
            LOG.info('attempting to load notification handler for %s:%s',
                     self.plugin_namespace, ep.name)
            try:
                # FIXME(dhellmann): Currently assumes all plugins are
                # enabled when they are discovered and
                # importable. Need to add check against global
                # configuration flag and check that asks the plugin if
                # it should be enabled.
                plugin_class = ep.load()
                plugin = plugin_class()
                self.topics.update(plugin.topics)
                for event_type in plugin.get_event_types():
                    LOG.info('subscribing %s handler to %s events',
                             ep.name, event_type)
                    self.handlers.setdefault(event_type, []).append(plugin)
            except Exception as err:
                LOG.warning('Failed to load notification handler %s: %s',
                            ep.name, err)
                LOG.exception(err)
        if not self.handlers:
            LOG.warning('Failed to load any notification handlers for %s',
                        self.plugin_namespace)

    def notify(self, topic, body):
        """Dispatch the notification to the appropriate handler
        and publish the counters returned.
        """
        event_type = body.get('event_type')
        LOG.info('NOTIFICATION: %s', event_type)
        for handler in self.handlers.get(event_type, []):
            if topic in handler.topics:
                for c in handler.process_notification(body):
                    LOG.info('COUNTER: %s', c)
                    # FIXME(dhellmann): Spawn green thread?
                    self.publish_func(c)
        return
