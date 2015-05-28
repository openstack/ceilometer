#
# Copyright 2013 eNovance
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
"""Log alarm notifier."""

from oslo_log import log

from ceilometer.alarm import notifier
from ceilometer.i18n import _

LOG = log.getLogger(__name__)


class LogAlarmNotifier(notifier.AlarmNotifier):
    "Log alarm notifier."""

    @staticmethod
    def notify(action, alarm_id, alarm_name, severity, previous, current,
               reason, reason_data):
        LOG.info(_(
            "Notifying alarm %(alarm_name)s %(alarm_id)s of %(severity)s "
            "priority from %(previous)s to %(current)s with action %(action)s"
            " because %(reason)s.") % ({'alarm_name': alarm_name,
                                        'alarm_id': alarm_id,
                                        'severity': severity,
                                        'previous': previous,
                                        'current': current,
                                        'action': action,
                                        'reason': reason}))
