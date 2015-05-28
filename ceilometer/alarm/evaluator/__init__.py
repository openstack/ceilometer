#
# Copyright 2013 eNovance <licensing@enovance.com>
#
# Authors: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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
import datetime

from ceilometerclient import client as ceiloclient
import croniter
from oslo_config import cfg
from oslo_log import log
from oslo_utils import timeutils
import pytz
import six

from ceilometer.i18n import _


LOG = log.getLogger(__name__)

UNKNOWN = 'insufficient data'
OK = 'ok'
ALARM = 'alarm'

cfg.CONF.import_opt('http_timeout', 'ceilometer.service')
cfg.CONF.import_group('service_credentials', 'ceilometer.service')


@six.add_metaclass(abc.ABCMeta)
class Evaluator(object):
    """Base class for alarm rule evaluator plugins."""

    def __init__(self, notifier):
        self.notifier = notifier
        self.api_client = None

    @property
    def _client(self):
        """Construct or reuse an authenticated API client."""
        if not self.api_client:
            auth_config = cfg.CONF.service_credentials
            creds = dict(
                os_auth_url=auth_config.os_auth_url,
                os_region_name=auth_config.os_region_name,
                os_tenant_name=auth_config.os_tenant_name,
                os_password=auth_config.os_password,
                os_username=auth_config.os_username,
                os_cacert=auth_config.os_cacert,
                os_endpoint_type=auth_config.os_endpoint_type,
                insecure=auth_config.insecure,
                timeout=cfg.CONF.http_timeout,
            )
            self.api_client = ceiloclient.get_client(2, **creds)
        return self.api_client

    def _refresh(self, alarm, state, reason, reason_data):
        """Refresh alarm state."""
        try:
            previous = alarm.state
            if previous != state:
                LOG.info(_('alarm %(id)s transitioning to %(state)s because '
                           '%(reason)s') % {'id': alarm.alarm_id,
                                            'state': state,
                                            'reason': reason})

                self._client.alarms.set_state(alarm.alarm_id, state=state)
            alarm.state = state
            if self.notifier:
                self.notifier.notify(alarm, previous, reason, reason_data)
        except Exception:
            # retry will occur naturally on the next evaluation
            # cycle (unless alarm state reverts in the meantime)
            LOG.exception(_('alarm state update failed'))

    @classmethod
    def within_time_constraint(cls, alarm):
        """Check whether the alarm is within at least one of its time limits.

        If there are none, then the answer is yes.
        """
        if not alarm.time_constraints:
            return True

        now_utc = timeutils.utcnow().replace(tzinfo=pytz.utc)
        for tc in alarm.time_constraints:
            tz = pytz.timezone(tc['timezone']) if tc['timezone'] else None
            now_tz = now_utc.astimezone(tz) if tz else now_utc
            start_cron = croniter.croniter(tc['start'], now_tz)
            if cls._is_exact_match(start_cron, now_tz):
                return True
            # start_cron.cur has changed in _is_exact_match(),
            # croniter cannot recover properly in some corner case.
            start_cron = croniter.croniter(tc['start'], now_tz)
            latest_start = start_cron.get_prev(datetime.datetime)
            duration = datetime.timedelta(seconds=tc['duration'])
            if latest_start <= now_tz <= latest_start + duration:
                return True
        return False

    @staticmethod
    def _is_exact_match(cron, ts):
        """Handle edge in case when both parameters are equal.

        Handle edge case where if the timestamp is the same as the
        cron point in time to the minute, croniter returns the previous
        start, not the current. We can check this by first going one
        step back and then one step forward and check if we are
        at the original point in time.
        """
        cron.get_prev()
        diff = timeutils.total_seconds(ts - cron.get_next(datetime.datetime))
        return abs(diff) < 60  # minute precision

    @abc.abstractmethod
    def evaluate(self, alarm):
        """Interface definition.

        evaluate an alarm
        alarm Alarm: an instance of the Alarm
        """
