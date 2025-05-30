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

import ceilometer.alarm.discovery
import ceilometer.cmd.polling
import ceilometer.compute.discovery
import ceilometer.compute.virt.inspector
import ceilometer.compute.virt.libvirt.utils
import ceilometer.event.converter
import ceilometer.image.discovery
import ceilometer.ipmi.pollsters
import ceilometer.keystone_client
import ceilometer.meter.notifications
import ceilometer.neutron_client
import ceilometer.notification
import ceilometer.nova_client
import ceilometer.objectstore.rgw
import ceilometer.objectstore.swift
import ceilometer.pipeline.base
import ceilometer.polling.manager
import ceilometer.publisher.messaging
import ceilometer.publisher.utils
import ceilometer.sample
import ceilometer.utils
import ceilometer.volume.discovery


OPTS = [
    cfg.HostAddressOpt('host',
                       default=socket.gethostname(),
                       sample_default='<your_hostname>',
                       help='Hostname, FQDN or IP address of this host. '
                            'Must be valid within AMQP key.'),
    cfg.IntOpt('http_timeout',
               default=600,
               deprecated_for_removal=True,
               deprecated_reason='This option has no effect',
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
         itertools.chain(ceilometer.cmd.polling.CLI_OPTS,
                         ceilometer.compute.virt.inspector.OPTS,
                         ceilometer.compute.virt.libvirt.utils.OPTS,
                         ceilometer.objectstore.swift.OPTS,
                         ceilometer.pipeline.base.OPTS,
                         ceilometer.polling.manager.POLLING_OPTS,
                         ceilometer.sample.OPTS,
                         ceilometer.utils.OPTS,
                         OPTS)),
        ('compute', ceilometer.compute.discovery.OPTS),
        ('coordination', [
            cfg.StrOpt(
                'backend_url',
                secret=True,
                help='The backend URL to use for distributed coordination. If '
                'left empty, per-deployment central agent and per-host '
                'compute agent won\'t do workload '
                'partitioning and will only function correctly if a '
                'single instance of that service is running.')
        ]),
        ('event', ceilometer.event.converter.OPTS),
        ('ipmi', ceilometer.ipmi.pollsters.OPTS),
        ('meter', ceilometer.meter.notifications.OPTS),
        ('notification',
         itertools.chain(ceilometer.notification.OPTS,
                         ceilometer.notification.EXCHANGES_OPTS)),
        ('polling', ceilometer.polling.manager.POLLING_OPTS),
        ('publisher', ceilometer.publisher.utils.OPTS),
        ('publisher_notifier', ceilometer.publisher.messaging.NOTIFIER_OPTS),
        ('rgw_admin_credentials', ceilometer.objectstore.rgw.CREDENTIAL_OPTS),
        ('rgw_client', ceilometer.objectstore.rgw.CLIENT_OPTS),
        ('service_types',
         itertools.chain(ceilometer.alarm.discovery.SERVICE_OPTS,
                         ceilometer.image.discovery.SERVICE_OPTS,
                         ceilometer.neutron_client.SERVICE_OPTS,
                         ceilometer.nova_client.SERVICE_OPTS,
                         ceilometer.objectstore.rgw.SERVICE_OPTS,
                         ceilometer.objectstore.swift.SERVICE_OPTS,
                         ceilometer.volume.discovery.SERVICE_OPTS,))
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
