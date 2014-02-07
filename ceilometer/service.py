#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012-2014 eNovance <licensing@enovance.com>
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

import eventlet
from oslo.config import cfg
from stevedore import named

from ceilometer.openstack.common import gettextutils
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import rpc


OPTS = [
    cfg.StrOpt('host',
               default=socket.gethostname(),
               help='Name of this node, which must be valid in an AMQP '
               'key. Can be an opaque identifier. For ZeroMQ only, must '
               'be a valid host name, FQDN, or IP address.'),
    cfg.MultiStrOpt('dispatcher',
                    deprecated_group="collector",
                    default=['database'],
                    help='Dispatcher to process data.'),
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
               default=os.environ.get('OS_CACERT', None),
               help='Certificate chain for SSL validation.'),
    cfg.StrOpt('os-auth-url',
               deprecated_group="DEFAULT",
               default=os.environ.get('OS_AUTH_URL',
                                      'http://localhost:5000/v2.0'),
               help='Auth URL to use for OpenStack service access.'),
    cfg.StrOpt('os-region-name',
               deprecated_group="DEFAULT",
               default=os.environ.get('OS_REGION_NAME', None),
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


LOG = log.getLogger(__name__)


class DispatchedService(object):

    DISPATCHER_NAMESPACE = 'ceilometer.dispatcher'

    def __init__(self, *args, **kwargs):
        super(DispatchedService, self).__init__(*args, **kwargs)
        LOG.debug(_('loading dispatchers from %s'),
                  self.DISPATCHER_NAMESPACE)
        self.dispatcher_manager = named.NamedExtensionManager(
            namespace=self.DISPATCHER_NAMESPACE,
            names=cfg.CONF.dispatcher,
            invoke_on_load=True,
            invoke_args=[cfg.CONF])
        if not list(self.dispatcher_manager):
            LOG.warning(_('Failed to load any dispatchers for %s'),
                        self.DISPATCHER_NAMESPACE)


def prepare_service(argv=None):
    # NOTE(jd) We need to monkey patch the socket module for, at least,
    # oslo.rpc, otherwise everything's blocked on its first read()
    eventlet.monkey_patch(socket=True)
    gettextutils.install('ceilometer', lazy=True)
    rpc.set_defaults(control_exchange='ceilometer')
    cfg.set_defaults(log.log_opts,
                     default_log_levels=['amqplib=WARN',
                                         'qpid.messaging=INFO',
                                         'sqlalchemy=WARN',
                                         'keystoneclient=INFO',
                                         'stevedore=INFO',
                                         'eventlet.wsgi.server=WARN'
                                         ])
    if argv is None:
        argv = sys.argv
    cfg.CONF(argv[1:], project='ceilometer')
    log.setup('ceilometer')
