#
# Copyright 2014 eNovance
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
"""Rest alarm notifier with trusted authentication."""

from oslo_config import cfg
from six.moves.urllib import parse

from ceilometer.alarm.notifier import rest
from ceilometer import keystone_client


cfg.CONF.import_opt('http_timeout', 'ceilometer.service')
cfg.CONF.import_group('service_credentials', 'ceilometer.service')


class TrustRestAlarmNotifier(rest.RestAlarmNotifier):
    """Notifier supporting keystone trust authentication.

    This alarm notifier is intended to be used to call an endpoint using
    keystone authentication. It uses the ceilometer service user to
    authenticate using the trust ID provided.

    The URL must be in the form trust+http://trust-id@host/action.
    """

    @staticmethod
    def notify(action, alarm_id, alarm_name, severity, previous, current,
               reason, reason_data):
        trust_id = action.username

        client = keystone_client.get_v3_client(trust_id)

        # Remove the fake user
        netloc = action.netloc.split("@")[1]
        # Remove the trust prefix
        scheme = action.scheme[6:]

        action = parse.SplitResult(scheme, netloc, action.path, action.query,
                                   action.fragment)

        headers = {'X-Auth-Token': client.auth_token}
        rest.RestAlarmNotifier.notify(
            action, alarm_id, alarm_name, severity, previous, current, reason,
            reason_data, headers)
