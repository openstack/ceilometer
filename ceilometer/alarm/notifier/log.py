# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance
#
# Author: Julien Danjou <julien@danjou.info>
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

from ceilometer.alarm import notifier
from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)


class LogAlarmNotifier(notifier.AlarmNotifier):
    "Log alarm notifier."""

    def notify(action, alarm, state, reason):
        LOG.info("Notifying alarm %s in state %s with action %s because %s",
                 alarm, state, action, reason)
