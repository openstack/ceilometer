# -*- coding: utf-8 -*-
#
# Copyright 2012-2014 Julien Danjou
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

from oslo_config import cfg
from oslo_context import context
from oslo_utils import timeutils
from stevedore import extension

from ceilometer import pipeline
from ceilometer import sample
from ceilometer import service


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
                   help='Meter unit.'),
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
        extension.ExtensionManager('ceilometer.transformer'))

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
