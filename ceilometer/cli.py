#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012-2014 Julien Danjou
#
# Author: Julien Danjou <julien@danjou.info>
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

"""Command line tool for creating meter for Ceilometer.
"""
import logging
import sys

import eventlet
# NOTE(jd) We need to monkey patch the socket and select module for,
# at least, oslo.messaging, otherwise everything's blocked on its
# first read() or select(), thread need to be patched too, because
# oslo.messaging use threading.local
eventlet.monkey_patch(socket=True, select=True, thread=True)


from oslo.config import cfg

from ceilometer.alarm import service as alarm_service
from ceilometer.api import app
from ceilometer.central import manager as central_manager
from ceilometer import collector
from ceilometer.compute import manager as compute_manager
from ceilometer import notification
from ceilometer.openstack.common import context
from ceilometer.openstack.common import importutils
from ceilometer.openstack.common import service as os_service
from ceilometer.openstack.common import timeutils
from ceilometer import pipeline
from ceilometer import sample
from ceilometer import service
from ceilometer import storage
from ceilometer import transformer

OPTS = [
    cfg.StrOpt('evaluation_service',
               default='ceilometer.alarm.service.SingletonAlarmService',
               help='Class to launch as alarm evaluation service.'),
]

cfg.CONF.register_opts(OPTS, group='alarm')
cfg.CONF.import_opt('time_to_live', 'ceilometer.storage',
                    group='database')

LOG = logging.getLogger(__name__)


def alarm_notifier():
    service.prepare_service()
    os_service.launch(alarm_service.AlarmNotifierService()).wait()


def alarm_evaluator():
    service.prepare_service()
    eval_service = importutils.import_object(cfg.CONF.alarm.evaluation_service)
    os_service.launch(eval_service).wait()


def agent_central():
    service.prepare_service()
    os_service.launch(central_manager.AgentManager()).wait()


def agent_compute():
    service.prepare_service()
    os_service.launch(compute_manager.AgentManager()).wait()


def agent_notification():
    service.prepare_service()
    launcher = os_service.ProcessLauncher()
    launcher.launch_service(
        notification.NotificationService(),
        workers=service.get_workers('notification'))
    launcher.wait()


def api():
    service.prepare_service()
    srv = app.build_server()
    srv.serve_forever()


def collector_service():
    service.prepare_service()
    launcher = os_service.ProcessLauncher()
    launcher.launch_service(
        collector.CollectorService(),
        workers=service.get_workers('collector'))
    launcher.wait()


def storage_dbsync():
    service.prepare_service()
    storage.get_connection_from_config(cfg.CONF).upgrade()


def storage_expirer():
    service.prepare_service()
    if cfg.CONF.database.time_to_live > 0:
        LOG.debug(_("Clearing expired metering data"))
        storage_conn = storage.get_connection_from_config(cfg.CONF)
        storage_conn.clear_expired_metering_data(
            cfg.CONF.database.time_to_live)
    else:
        LOG.info(_("Nothing to clean, database time to live is disabled"))


def send_sample():
    cfg.CONF.register_cli_opts([
        cfg.StrOpt('sample-name',
                   short='n',
                   help='Meter name.',
                   required=True),
        cfg.StrOpt('sample-type',
                   short='y',
                   help='Meter type (gauge, delta, cumulative).',
                   default='gauge',
                   required=True),
        cfg.StrOpt('sample-unit',
                   short='U',
                   help='Meter unit.',
                   default=None),
        cfg.IntOpt('sample-volume',
                   short='l',
                   help='Meter volume value.',
                   default=1),
        cfg.StrOpt('sample-resource',
                   short='r',
                   help='Meter resource id.',
                   required=True),
        cfg.StrOpt('sample-user',
                   short='u',
                   help='Meter user id.'),
        cfg.StrOpt('sample-project',
                   short='p',
                   help='Meter project id.'),
        cfg.StrOpt('sample-timestamp',
                   short='i',
                   help='Meter timestamp.',
                   default=timeutils.utcnow().isoformat()),
        cfg.StrOpt('sample-metadata',
                   short='m',
                   help='Meter metadata.'),
    ])

    service.prepare_service()

    # Set up logging to use the console
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')
    console.setFormatter(formatter)
    root_logger = logging.getLogger('')
    root_logger.addHandler(console)
    root_logger.setLevel(logging.DEBUG)

    pipeline_manager = pipeline.setup_pipeline(
        transformer.TransformerExtensionManager(
            'ceilometer.transformer',
        ),
    )

    with pipeline_manager.publisher(context.get_admin_context()) as p:
        p([sample.Sample(
            name=cfg.CONF.sample_name,
            type=cfg.CONF.sample_type,
            unit=cfg.CONF.sample_unit,
            volume=cfg.CONF.sample_volume,
            user_id=cfg.CONF.sample_user,
            project_id=cfg.CONF.sample_project,
            resource_id=cfg.CONF.sample_resource,
            timestamp=cfg.CONF.sample_timestamp,
            resource_metadata=cfg.CONF.sample_metadata and eval(
                cfg.CONF.sample_metadata))])
