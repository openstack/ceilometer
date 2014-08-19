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
"""Base class for plugins used by the compute agent.
"""

import abc

from oslo.utils import timeutils
import six

from ceilometer import plugin


@six.add_metaclass(abc.ABCMeta)
class ComputePollster(plugin.PollsterBase):
    """Base class for plugins.

    It supports the polling API on the compute node.
    """

    @abc.abstractmethod
    def get_samples(self, manager, cache, resources):
        """Return a sequence of Counter instances from polling the resources.

        :param manager: The service manager invoking the plugin
        :param cache: A dictionary for passing data between plugins
        :param resources: The resources to examine (expected to be instances)
        """

    def _record_poll_time(self):
        """Method records current time as the poll time.

        :return: time in seconds since the last poll time was recorded
        """
        current_time = timeutils.utcnow()
        duration = None
        if hasattr(self, '_last_poll_time'):
            duration = timeutils.delta_seconds(self._last_poll_time,
                                               current_time)
        self._last_poll_time = current_time
        return duration
