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
import six.moves.urllib.parse as urlparse

from oslo.config import cfg

from ceilometer.alarm import notifier
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import jsonutils
from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)

REST_NOTIFIER_OPTS = [
    cfg.StrOpt('rest_notifier_certificate_file',
               default='',
               help='SSL Client certificate for REST notifier.'
               ),
    cfg.StrOpt('rest_notifier_certificate_key',
               default='',
               help='SSL Client private key for REST notifier.'
               ),
    cfg.BoolOpt('rest_notifier_ssl_verify',
                default=True,
                help='Whether to verify the SSL Server certificate when '
                'calling alarm action.'
                ),

]

cfg.CONF.register_opts(REST_NOTIFIER_OPTS, group="alarm")


class RestAlarmNotifier(notifier.AlarmNotifier):
    """Rest alarm notifier."""

    @staticmethod
    def notify(action, alarm_id, previous, current, reason, reason_data):
        LOG.info(_(
            "Notifying alarm %(alarm_id)s from %(previous)s "
            "to %(current)s with action %(action)s because "
            "%(reason)s") % ({'alarm_id': alarm_id, 'previous': previous,
                              'current': current, 'action': action,
                              'reason': reason}))
        body = {'alarm_id': alarm_id, 'previous': previous,
                'current': current, 'reason': reason,
                'reason_data': reason_data}
        kwargs = {'data': jsonutils.dumps(body)}

        if action.scheme == 'https':
            default_verify = int(cfg.CONF.alarm.rest_notifier_ssl_verify)
            options = urlparse.parse_qs(action.query)
            verify = bool(int(options.get('ceilometer-alarm-ssl-verify',
                                          [default_verify])[-1]))
            kwargs['verify'] = verify

            cert = cfg.CONF.alarm.rest_notifier_certificate_file
            key = cfg.CONF.alarm.rest_notifier_certificate_key
            if cert:
                kwargs['cert'] = (cert, key) if key else cert

        eventlet.spawn_n(requests.post, action.geturl(), **kwargs)
