# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance
#
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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
"""Rest alarm notifier."""

import eventlet
import requests

from oslo.config import cfg

from ceilometer.alarm import notifier
from ceilometer.openstack.common import jsonutils
from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)

REST_NOTIFIER_OPTS = [
    cfg.StrOpt('rest_notifier_certificate_file',
               default='',
               help='SSL Client certificate for REST notifier'
               ),
    cfg.StrOpt('rest_notifier_certificate_key',
               default='',
               help='SSL Client private key for REST notifier'
               ),
]

cfg.CONF.register_opts(REST_NOTIFIER_OPTS, group="alarm")


class RestAlarmNotifier(notifier.AlarmNotifier):
    """Rest alarm notifier."""

    def notify(self, action, alarm, state, reason):
        LOG.info("Notifying alarm %s in state %s with action %s because %s",
                 alarm, state, action, reason)
        body = {'state': state, 'reason': reason}
        kwargs = {'data': jsonutils.dumps(body)}

        cert = cfg.CONF.alarm.rest_notifier_certificate_file
        key = cfg.CONF.alarm.rest_notifier_certificate_key
        if action.scheme == 'https' and cert:
            kwargs['cert'] = (cert, key) if key else cert

        eventlet.spawn_n(requests.post, action.geturl(), **kwargs)
