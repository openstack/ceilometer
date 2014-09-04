#
# Copyright 2013-2014 eNovance
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
from oslo.config import cfg
from oslo.serialization import jsonutils
import requests
import six.moves.urllib.parse as urlparse

from ceilometer.alarm import notifier
from ceilometer.openstack.common import context
from ceilometer.openstack.common.gettextutils import _
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
    cfg.IntOpt('rest_notifier_max_retries',
               default=0,
               help='Number of retries for REST notifier',
               ),

]

cfg.CONF.register_opts(REST_NOTIFIER_OPTS, group="alarm")


class RestAlarmNotifier(notifier.AlarmNotifier):
    """Rest alarm notifier."""

    @staticmethod
    def notify(action, alarm_id, previous, current, reason, reason_data,
               headers=None):
        headers = headers or {}
        if not headers.get('x-openstack-request-id'):
            headers['x-openstack-request-id'] = context.generate_request_id()

        LOG.info(_(
            "Notifying alarm %(alarm_id)s from %(previous)s "
            "to %(current)s with action %(action)s because "
            "%(reason)s. request-id: %(request_id)s") %
            ({'alarm_id': alarm_id, 'previous': previous,
              'current': current, 'action': action,
              'reason': reason,
              'request_id': headers['x-openstack-request-id']}))
        body = {'alarm_id': alarm_id, 'previous': previous,
                'current': current, 'reason': reason,
                'reason_data': reason_data}
        headers['content-type'] = 'application/json'
        kwargs = {'data': jsonutils.dumps(body),
                  'headers': headers}

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

        # FIXME(rhonjo): Retries are automatically done by urllib3 in requests
        # library. However, there's no interval between retries in urllib3
        # implementation. It will be better to put some interval between
        # retries (future work).
        max_retries = cfg.CONF.alarm.rest_notifier_max_retries
        session = requests.Session()
        session.mount(action.geturl(),
                      requests.adapters.HTTPAdapter(max_retries=max_retries))
        eventlet.spawn_n(session.post, action.geturl(), **kwargs)
