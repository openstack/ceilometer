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
"""Simple logging storage backend.
"""

from oslo_log import log

from ceilometer.alarm.storage import base
from ceilometer.i18n import _LI

LOG = log.getLogger(__name__)


class Connection(base.Connection):
    """Log the data."""

    def upgrade(self):
        pass

    def clear(self):
        pass

    def get_alarms(self, name=None, user=None, state=None, meter=None,
                   project=None, enabled=None, alarm_id=None,
                   alarm_type=None, severity=None):
        """Yields a lists of alarms that match filters."""
        return []

    def create_alarm(self, alarm):
        """Create alarm."""
        return alarm

    def update_alarm(self, alarm):
        """Update alarm."""
        return alarm

    def delete_alarm(self, alarm_id):
        """Delete an alarm and its history data."""

    def clear_expired_alarm_history_data(self, alarm_history_ttl):
        """Clear expired alarm history data from the backend storage system.

        Clearing occurs according to the time-to-live.

        :param alarm_history_ttl: Number of seconds to keep alarm history
                                  records for.
        """
        LOG.info(_LI('Dropping alarm history data with TTL %d'),
                 alarm_history_ttl)
