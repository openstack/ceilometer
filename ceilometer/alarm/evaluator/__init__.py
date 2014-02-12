# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
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

from ceilometerclient import client as ceiloclient
from oslo.config import cfg
import six

from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)

UNKNOWN = 'insufficient data'
OK = 'ok'
ALARM = 'alarm'


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

    @abc.abstractmethod
    def evaluate(self, alarm):
        '''interface definition

        evaluate an alarm
        alarm Alarm: an instance of the Alarm
        '''
