# -*- encoding: utf-8 -*-
#
# Copyright 2014 OpenStack Foundation
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
from stevedore import driver

from ceilometer.alarm import service as alarm_service
from ceilometer.openstack.common import log
from ceilometer.openstack.common import service as os_service
from ceilometer import service


OPTS = [
    cfg.StrOpt('evaluation_service', default='default',
               help='Driver to use for alarm evaluation service. DEPRECATED: '
                    '"singleton" and "partitioned" alarm evaluator '
                    'services will be removed in Kilo in favour of the '
                    'default alarm evaluation service using tooz for '
                    'partitioning.'),
]

cfg.CONF.register_opts(OPTS, group='alarm')

LOG = log.getLogger(__name__)


def notifier():
    service.prepare_service()
    os_service.launch(alarm_service.AlarmNotifierService()).wait()


def evaluator():
    service.prepare_service()
    eval_service_mgr = driver.DriverManager(
        "ceilometer.alarm.evaluator_service",
        cfg.CONF.alarm.evaluation_service,
        invoke_on_load=True)
    LOG.debug("Alarm evaluator loaded: %s" %
              eval_service_mgr.driver.__class__.__name__)
    os_service.launch(eval_service_mgr.driver).wait()
