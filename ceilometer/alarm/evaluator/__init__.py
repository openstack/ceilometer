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

from oslo.config import cfg

from ceilometerclient import client as ceiloclient

from ceilometer.openstack.common import log
from ceilometer.openstack.common.gettextutils import _

LOG = log.getLogger(__name__)


class Evaluator(object):
    """Base class for alarm rule evaluator plugins."""

    __metaclass__ = abc.ABCMeta

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
                os_tenant_name=auth_config.os_tenant_name,
                os_password=auth_config.os_password,
                os_username=auth_config.os_username,
                cacert=auth_config.os_cacert,
                endpoint_type=auth_config.os_endpoint_type,
            )
            self.api_client = ceiloclient.get_client(2, **creds)
        return self.api_client

    def _refresh(self, alarm, state, reason):
        """Refresh alarm state."""
        try:
            previous = alarm.state
            if previous != state:
                LOG.info(_('alarm %(id)s transitioning to %(state)s because '
                           '%(reason)s') % {'id': alarm.alarm_id,
                                            'state': state,
                                            'reason': reason})

                self._client.alarms.update(alarm.alarm_id, **dict(state=state))
            alarm.state = state
            if self.notifier:
                self.notifier.notify(alarm, previous, reason)
        except Exception:
            # retry will occur naturally on the next evaluation
            # cycle (unless alarm state reverts in the meantime)
            LOG.exception(_('alarm state update failed'))

    @abc.abstractmethod
    def evaluate(self, alarm):
        pass
