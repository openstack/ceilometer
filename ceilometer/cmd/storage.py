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

from oslo_config import cfg
from oslo_log import log
import tenacity

from ceilometer import service

LOG = log.getLogger(__name__)


def upgrade():
    conf = cfg.ConfigOpts()
    conf.register_cli_opts([
        cfg.BoolOpt('skip-gnocchi-resource-types',
                    help='Skip gnocchi resource-types upgrade.',
                    default=False),
        cfg.IntOpt('retry',
                   min=0,
                   help='Number of times to retry on failure. '
                   'Default is to retry forever.'),
    ])

    service.prepare_service(conf=conf)
    if conf.skip_gnocchi_resource_types:
        LOG.info("Skipping Gnocchi resource types upgrade")
    else:
        LOG.debug("Upgrading Gnocchi resource types")
        from ceilometer import gnocchi_client
        from gnocchiclient import exceptions
        if conf.retry is None:
            stop = tenacity.stop_never
        else:
            stop = tenacity.stop_after_attempt(conf.retry)
        tenacity.Retrying(
            stop=stop,
            retry=tenacity.retry_if_exception_type((
                exceptions.ConnectionFailure,
                exceptions.UnknownConnectionError,
                exceptions.ConnectionTimeout,
                exceptions.SSLError,
            ))
        )(gnocchi_client.upgrade_resource_types, conf)
