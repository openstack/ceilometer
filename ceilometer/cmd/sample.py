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
from oslo_utils import timeutils
from stevedore import extension

from ceilometer import pipeline
from ceilometer import sample
from ceilometer import service


def send_sample():
    conf = cfg.ConfigOpts()
    conf.register_cli_opts([
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

    service.prepare_service(conf=conf)

    # Set up logging to use the console
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')
    console.setFormatter(formatter)
    root_logger = logging.getLogger('')
    root_logger.addHandler(console)
    root_logger.setLevel(logging.DEBUG)

    pipeline_manager = pipeline.setup_pipeline(
        conf, extension.ExtensionManager('ceilometer.transformer'))

    with pipeline_manager.publisher() as p:
        p([sample.Sample(
            name=conf.sample_name,
            type=conf.sample_type,
            unit=conf.sample_unit,
            volume=conf.sample_volume,
            user_id=conf.sample_user,
            project_id=conf.sample_project,
            resource_id=conf.sample_resource,
            timestamp=conf.sample_timestamp,
            resource_metadata=conf.sample_metadata and eval(
                conf.sample_metadata))])
