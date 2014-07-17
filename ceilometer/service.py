#!/usr/bin/env python
#
# Copyright 2012-2014 eNovance <licensing@enovance.com>
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
import socket
import sys

from oslo.config import cfg

from ceilometer import messaging
from ceilometer.openstack.common import gettextutils
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer import utils


OPTS = [
    cfg.StrOpt('host',
               default=socket.gethostname(),
               help='Name of this node, which must be valid in an AMQP '
               'key. Can be an opaque identifier. For ZeroMQ only, must '
               'be a valid host name, FQDN, or IP address.'),
    cfg.IntOpt('collector_workers',
               default=1,
               help='Number of workers for collector service. A single '
               'collector is enabled by default.'),
    cfg.IntOpt('notification_workers',
               default=1,
               help='Number of workers for notification service. A single '
               'notification agent is enabled by default.'),
]
cfg.CONF.register_opts(OPTS)

CLI_OPTIONS = [
    cfg.StrOpt('os-username',
               deprecated_group="DEFAULT",
               default=os.environ.get('OS_USERNAME', 'ceilometer'),
               help='User name to use for OpenStack service access.'),
    cfg.StrOpt('os-password',
               deprecated_group="DEFAULT",
               secret=True,
               default=os.environ.get('OS_PASSWORD', 'admin'),
               help='Password to use for OpenStack service access.'),
    cfg.StrOpt('os-tenant-id',
               deprecated_group="DEFAULT",
               default=os.environ.get('OS_TENANT_ID', ''),
               help='Tenant ID to use for OpenStack service access.'),
    cfg.StrOpt('os-tenant-name',
               deprecated_group="DEFAULT",
               default=os.environ.get('OS_TENANT_NAME', 'admin'),
               help='Tenant name to use for OpenStack service access.'),
    cfg.StrOpt('os-cacert',
               default=os.environ.get('OS_CACERT'),
               help='Certificate chain for SSL validation.'),
    cfg.StrOpt('os-auth-url',
               deprecated_group="DEFAULT",
               default=os.environ.get('OS_AUTH_URL',
                                      'http://localhost:5000/v2.0'),
               help='Auth URL to use for OpenStack service access.'),
    cfg.StrOpt('os-region-name',
               deprecated_group="DEFAULT",
               default=os.environ.get('OS_REGION_NAME'),
               help='Region name to use for OpenStack service endpoints.'),
    cfg.StrOpt('os-endpoint-type',
               default=os.environ.get('OS_ENDPOINT_TYPE', 'publicURL'),
               help='Type of endpoint in Identity service catalog to use for '
                    'communication with OpenStack services.'),
    cfg.BoolOpt('insecure',
                default=False,
                help='Disables X.509 certificate validation when an '
                     'SSL connection to Identity Service is established.'),
]
cfg.CONF.register_cli_opts(CLI_OPTIONS, group="service_credentials")

cfg.CONF.import_opt('default_log_levels',
                    'ceilometer.openstack.common.log')

LOG = log.getLogger(__name__)


class WorkerException(Exception):
    """Exception for errors relating to service workers."""


def get_workers(name):
    workers = (cfg.CONF.get('%s_workers' % name) or
               utils.cpu_count())
    if workers and workers < 1:
        msg = (_("%(worker_name)s value of %(workers)s is invalid, "
                 "must be greater than 0") %
               {'worker_name': '%s_workers' % name, 'workers': str(workers)})
        raise WorkerException(msg)
    return workers


def prepare_service(argv=None):
    gettextutils.install('ceilometer')
    gettextutils.enable_lazy()
    log_levels = (cfg.CONF.default_log_levels +
                  ['stevedore=INFO', 'keystoneclient=INFO'])
    cfg.set_defaults(log.log_opts,
                     default_log_levels=log_levels)
    if argv is None:
        argv = sys.argv
    cfg.CONF(argv[1:], project='ceilometer')
    log.setup('ceilometer')
    messaging.setup()
