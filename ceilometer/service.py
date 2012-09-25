#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
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

import os

from nova import flags

from ceilometer.openstack.common import log
from ceilometer.openstack.common import cfg

cfg.CONF.register_opts([
    cfg.IntOpt('periodic_interval',
               default=60,
               help='seconds between running periodic tasks')
])

CLI_OPTIONS = [
    cfg.StrOpt('os-username',
               default=os.environ.get('OS_USERNAME', 'glance'),
               help='Username to use for openstack service access'),
    cfg.StrOpt('os-password',
               default=os.environ.get('OS_PASSWORD', 'admin'),
               help='Password to use for openstack service access'),
    cfg.StrOpt('os-tenant-id',
               default=os.environ.get('OS_TENANT_ID', ''),
               help='Tenant ID to use for openstack service access'),
    cfg.StrOpt('os-tenant-name',
               default=os.environ.get('OS_TENANT_NAME', 'admin'),
               help='Tenant name to use for openstack service access'),
    cfg.StrOpt('os-auth-url',
               default=os.environ.get('OS_AUTH_URL',
                                      'http://localhost:5000/v2.0'),
               help='Auth URL to use for openstack service access'),
]
cfg.CONF.register_cli_opts(CLI_OPTIONS)


def _sanitize_cmd_line(argv):
    """Remove non-nova CLI options from argv."""
    cli_opt_names = ['--%s' % o.name for o in CLI_OPTIONS]
    return [a for a in argv if a in cli_opt_names]


def prepare_service(argv=[]):
    cfg.CONF(argv[1:])
    # FIXME(dhellmann): We must set up the nova.flags module in order
    # to have the RPC and DB access work correctly because we are
    # still using the Service object out of nova directly. We need to
    # move that into openstack.common.
    flags.parse_args(_sanitize_cmd_line(argv))
    log.setup('ceilometer')
