#
# Copyright 2013 eNovance <licensing@enovance.com>
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

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class AlarmNotifier(object):
    """Base class for alarm notifier plugins."""

    @abc.abstractmethod
    def notify(self, action, alarm_id, alarm_name, severity, previous,
               current, reason, reason_data):
        """Notify that an alarm has been triggered.

        :param action: The action that is being attended, as a parsed URL.
        :param alarm_id: The triggered alarm.
        :param alarm_name: The name of triggered alarm.
        :param severity: The level of triggered alarm
        :param previous: The previous state of the alarm.
        :param current: The current state of the alarm.
        :param reason: The reason the alarm changed its state.
        :param reason_data: A dict representation of the reason.
        """
