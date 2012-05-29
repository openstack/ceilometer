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


class NotificationBase(object):
    """Base class for plugins that support the notification API."""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_event_types(self):
        """Return a sequence of strings defining the event types to be
        given to this plugin."""

    @abc.abstractmethod
    def process_notification(self, message):
        """Return a sequence of Counter instances for the given message."""


class PollsterBase(object):
    """Base class for plugins that support the polling API."""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_counters(self, manager, context):
        """Return a sequence of Counter instances from polling the
        resources."""
