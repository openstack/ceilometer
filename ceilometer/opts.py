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
import itertools
import socket

from keystoneauth1 import loading
from oslo_config import cfg

import ceilometer.agent.manager
import ceilometer.api.app
import ceilometer.api.controllers.v2.root
import ceilometer.collector
import ceilometer.compute.discovery
import ceilometer.compute.virt.inspector
import ceilometer.compute.virt.libvirt.utils
import ceilometer.compute.virt.vmware.inspector
import ceilometer.compute.virt.xenapi.inspector
import ceilometer.dispatcher
import ceilometer.dispatcher.file
import ceilometer.dispatcher.gnocchi_opts
import ceilometer.dispatcher.http
import ceilometer.event.converter
import ceilometer.exchange_control
import ceilometer.hardware.discovery
import ceilometer.hardware.pollsters.generic
import ceilometer.image.discovery
import ceilometer.ipmi.notifications.ironic
import ceilometer.ipmi.platform.intel_node_manager
import ceilometer.ipmi.pollsters
import ceilometer.keystone_client
import ceilometer.meter.notifications
import ceilometer.middleware
import ceilometer.neutron_client
import ceilometer.notification
import ceilometer.nova_client
import ceilometer.objectstore.rgw
import ceilometer.objectstore.swift
import ceilometer.pipeline
import ceilometer.publisher.messaging
import ceilometer.publisher.utils
import ceilometer.sample
import ceilometer.storage
import ceilometer.utils
import ceilometer.volume.discovery


OPTS = [
    cfg.HostAddressOpt('host',
                       default=socket.gethostname(),
                       sample_default='<your_hostname>',
                       help='Name of this node, which must be valid in an '
                       'AMQP key. Can be an opaque identifier. For ZeroMQ '
                       'only, must be a valid host name, FQDN, or IP '
                       'address.'),
    cfg.IntOpt('http_timeout',
               default=600,
               help='Timeout seconds for HTTP requests. Set it to None to '
                    'disable timeout.'),
    cfg.IntOpt('max_parallel_requests',
               default=64,
               min=1,
               help='Maximum number of parallel requests for '
               'services to handle at the same time.'),
]


def list_opts():
    # FIXME(sileht): readd pollster namespaces in the generated configfile
    # This have been removed due to a recursive import issue
    return [
        ('DEFAULT',
         itertools.chain(ceilometer.agent.manager.OPTS,
                         ceilometer.api.app.OPTS,
                         ceilometer.compute.virt.inspector.OPTS,
                         ceilometer.compute.virt.libvirt.utils.OPTS,
                         ceilometer.dispatcher.OPTS,
                         ceilometer.ipmi.notifications.ironic.OPTS,
                         ceilometer.nova_client.OPTS,
                         ceilometer.objectstore.swift.OPTS,
                         ceilometer.pipeline.OPTS,
                         ceilometer.sample.OPTS,
                         ceilometer.utils.OPTS,
                         ceilometer.exchange_control.EXCHANGE_OPTS,
                         OPTS)),
        ('api', itertools.chain(ceilometer.api.app.API_OPTS,
                                ceilometer.api.controllers.v2.root.API_OPTS)),
        ('collector', ceilometer.collector.OPTS),
        ('compute', ceilometer.compute.discovery.OPTS),
        ('coordination', [
            cfg.StrOpt(
                'backend_url',
                help='The backend URL to use for distributed coordination. If '
                'left empty, per-deployment central agent and per-host '
                'compute agent won\'t do workload '
                'partitioning and will only function correctly if a '
                'single instance of that service is running.'),
            cfg.FloatOpt(
                'check_watchers',
                default=10.0,
                help='Number of seconds between checks to see if group '
                'membership has changed'),
        ]),
        ('database', ceilometer.storage.OPTS),
        ('dispatcher_file', ceilometer.dispatcher.file.OPTS),
        ('dispatcher_http', ceilometer.dispatcher.http.http_dispatcher_opts),
        ('dispatcher_gnocchi',
         ceilometer.dispatcher.gnocchi_opts.dispatcher_opts),
        ('event', ceilometer.event.converter.OPTS),
        ('hardware', itertools.chain(
            ceilometer.hardware.discovery.OPTS,
            ceilometer.hardware.pollsters.generic.OPTS)),
        ('ipmi',
         itertools.chain(ceilometer.ipmi.platform.intel_node_manager.OPTS,
                         ceilometer.ipmi.pollsters.OPTS)),
        ('meter', ceilometer.meter.notifications.OPTS),
        ('notification',
         itertools.chain(ceilometer.notification.OPTS,
                         ceilometer.notification.EXCHANGES_OPTS)),
        ('polling', ceilometer.agent.manager.POLLING_OPTS),
        ('publisher', ceilometer.publisher.utils.OPTS),
        ('publisher_notifier', ceilometer.publisher.messaging.NOTIFIER_OPTS),
        ('rgw_admin_credentials', ceilometer.objectstore.rgw.CREDENTIAL_OPTS),
        ('service_types',
         itertools.chain(ceilometer.image.discovery.SERVICE_OPTS,
                         ceilometer.neutron_client.SERVICE_OPTS,
                         ceilometer.nova_client.SERVICE_OPTS,
                         ceilometer.objectstore.rgw.SERVICE_OPTS,
                         ceilometer.objectstore.swift.SERVICE_OPTS,
                         ceilometer.volume.discovery.SERVICE_OPTS,)),
        ('vmware', ceilometer.compute.virt.vmware.inspector.OPTS),
        ('xenapi', ceilometer.compute.virt.xenapi.inspector.OPTS),
    ]


def list_keystoneauth_opts():
    # NOTE(sileht): the configuration file contains only the options
    # for the password plugin that handles keystone v2 and v3 API
    # with discovery. But other options are possible.
    return [('service_credentials', itertools.chain(
        loading.get_auth_common_conf_options(),
        loading.get_auth_plugin_conf_options('password'),
        ceilometer.keystone_client.CLI_OPTS
    ))]
