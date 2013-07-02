# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc
#
# Author: Eoghan Glynn <eglynn@redhat.com>
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

from oslo.config import cfg
from stevedore import extension

from ceilometer.service import prepare_service
from ceilometer.openstack.common import log
from ceilometer.openstack.common import service as os_service
from ceilometerclient import client as ceiloclient

OPTS = [
    cfg.IntOpt('threshold_evaluation_interval',
               default=60,
               help='Period of threshold evaluation cycle, should'
                    ' be >= than configured pipeline interval for'
                    ' collection of underlying metrics.'),
]

cfg.CONF.register_opts(OPTS, group='alarm')

LOG = log.getLogger(__name__)


class SingletonAlarmService(os_service.Service):

    ALARM_NAMESPACE = 'ceilometer.alarm'

    def __init__(self):
        super(SingletonAlarmService, self).__init__()
        self.extension_manager = extension.ExtensionManager(
            namespace=self.ALARM_NAMESPACE,
            invoke_on_load=True,
        )

    def start(self):
        super(SingletonAlarmService, self).start()
        for ext in self.extension_manager.extensions:
            if ext.name == 'threshold_eval':
                self.threshold_eval = ext.obj
                interval = cfg.CONF.alarm.threshold_evaluation_interval
                args = [ext.obj, self._client()]
                self.tg.add_timer(
                    interval,
                    self._evaluate_all_alarms,
                    0,
                    *args)
                break
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    @staticmethod
    def _client():
        auth_config = cfg.CONF.service_credentials
        creds = dict(
            os_auth_url=auth_config.os_auth_url,
            os_tenant_name=auth_config.os_tenant_name,
            os_password=auth_config.os_password,
            os_username=auth_config.os_username
        )
        return ceiloclient.get_client(2, **creds)

    @staticmethod
    def _evaluate_all_alarms(threshold_eval, api_client):
        try:
            alarms = api_client.alarms.list()
            threshold_eval.assign_alarms(alarms)
            threshold_eval.evaluate()
        except Exception:
            LOG.exception(_('threshold evaluation cycle failed'))


def singleton_alarm():
    prepare_service()
    os_service.launch(SingletonAlarmService()).wait()
