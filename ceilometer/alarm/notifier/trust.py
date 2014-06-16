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

from keystoneclient.v3 import client as keystone_client
from oslo.config import cfg
from six.moves.urllib import parse

from ceilometer.alarm.notifier import rest


class TrustRestAlarmNotifier(rest.RestAlarmNotifier):
    """Notifier supporting keystone trust authentication.

    This alarm notifier is intended to be used to call an endpoint using
    keystone authentication. It uses the ceilometer service user to
    authenticate using the trust ID provided.

    The URL must be in the form trust+http://trust-id@host/action.
    """

    @staticmethod
    def notify(action, alarm_id, previous, current, reason, reason_data):
        trust_id = action.username

        auth_url = cfg.CONF.service_credentials.os_auth_url.replace(
            "v2.0", "v3")
        client = keystone_client.Client(
            username=cfg.CONF.service_credentials.os_username,
            password=cfg.CONF.service_credentials.os_password,
            cacert=cfg.CONF.service_credentials.os_cacert,
            auth_url=auth_url,
            region_name=cfg.CONF.service_credentials.os_region_name,
            insecure=cfg.CONF.service_credentials.insecure,
            trust_id=trust_id)

        # Remove the fake user
        netloc = action.netloc.split("@")[1]
        # Remove the trust prefix
        scheme = action.scheme[6:]

        action = parse.SplitResult(scheme, netloc, action.path, action.query,
                                   action.fragment)

        headers = {'X-Auth-Token': client.auth_token}
        rest.RestAlarmNotifier.notify(
            action, alarm_id, previous, current, reason, reason_data, headers)
