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

from keystoneauth1 import loading

import ceilometer.agent.manager
import ceilometer.api
import ceilometer.api.app
import ceilometer.cmd.polling
import ceilometer.collector
import ceilometer.compute.discovery
import ceilometer.compute.notifications
import ceilometer.compute.util
import ceilometer.compute.virt.inspector
import ceilometer.compute.virt.libvirt.inspector
import ceilometer.compute.virt.vmware.inspector
import ceilometer.compute.virt.xenapi.inspector
import ceilometer.coordination
import ceilometer.dispatcher
import ceilometer.dispatcher.file
import ceilometer.dispatcher.gnocchi
import ceilometer.energy.kwapi
import ceilometer.event.converter
import ceilometer.hardware.discovery
import ceilometer.image.glance
import ceilometer.ipmi.notifications.ironic
import ceilometer.ipmi.platform.intel_node_manager
import ceilometer.ipmi.pollsters
import ceilometer.keystone_client
import ceilometer.meter.notifications
import ceilometer.middleware
import ceilometer.network.notifications
import ceilometer.neutron_client
import ceilometer.notification
import ceilometer.nova_client
import ceilometer.objectstore.rgw
import ceilometer.objectstore.swift
import ceilometer.pipeline
import ceilometer.publisher.messaging
import ceilometer.publisher.utils
import ceilometer.sample
import ceilometer.service
import ceilometer.storage
import ceilometer.utils


def list_opts():
    return [
        ('DEFAULT',
         itertools.chain(ceilometer.agent.manager.OPTS,
                         ceilometer.api.app.OPTS,
                         ceilometer.cmd.polling.CLI_OPTS,
                         ceilometer.compute.notifications.OPTS,
                         ceilometer.compute.util.OPTS,
                         ceilometer.compute.virt.inspector.OPTS,
                         ceilometer.compute.virt.libvirt.inspector.OPTS,
                         ceilometer.dispatcher.OPTS,
                         ceilometer.image.glance.OPTS,
                         ceilometer.ipmi.notifications.ironic.OPTS,
                         ceilometer.middleware.OPTS,
                         ceilometer.network.notifications.OPTS,
                         ceilometer.nova_client.OPTS,
                         ceilometer.objectstore.swift.OPTS,
                         ceilometer.pipeline.OPTS,
                         ceilometer.sample.OPTS,
                         ceilometer.service.OPTS,
                         ceilometer.storage.OLD_OPTS,
                         ceilometer.storage.CLI_OPTS,
                         ceilometer.utils.OPTS,)),
        ('api',
         itertools.chain(ceilometer.api.OPTS,
                         ceilometer.api.app.API_OPTS,
                         [ceilometer.service.API_OPT])),
        # deprecated path, new one is 'polling'
        ('central', ceilometer.agent.manager.OPTS),
        ('collector',
         itertools.chain(ceilometer.collector.OPTS,
                         [ceilometer.service.COLL_OPT])),
        ('compute', ceilometer.compute.discovery.OPTS),
        ('coordination', ceilometer.coordination.OPTS),
        ('database', ceilometer.storage.OPTS),
        ('dispatcher_file', ceilometer.dispatcher.file.OPTS),
        ('dispatcher_gnocchi', ceilometer.dispatcher.gnocchi.dispatcher_opts),
        ('event', ceilometer.event.converter.OPTS),
        ('exchange_control', ceilometer.exchange_control.EXCHANGE_OPTS),
        ('hardware', ceilometer.hardware.discovery.OPTS),
        ('ipmi',
         itertools.chain(ceilometer.ipmi.platform.intel_node_manager.OPTS,
                         ceilometer.ipmi.pollsters.OPTS)),
        ('meter', ceilometer.meter.notifications.OPTS),
        ('notification',
         itertools.chain(ceilometer.notification.OPTS,
                         [ceilometer.service.NOTI_OPT])),
        ('polling', ceilometer.agent.manager.OPTS),
        ('publisher', ceilometer.publisher.utils.OPTS),
        ('publisher_notifier', ceilometer.publisher.messaging.NOTIFIER_OPTS),
        ('rgw_admin_credentials', ceilometer.objectstore.rgw.CREDENTIAL_OPTS),
        # NOTE(sileht): the configuration file contains only the options
        # for the password plugin that handles keystone v2 and v3 API
        # with discovery. But other options are possible.
        # Also, the default loaded plugin is password-ceilometer-legacy for
        # backward compatibility
        ('service_credentials', (
            ceilometer.keystone_client.CLI_OPTS +
            loading.get_auth_common_conf_options() +
            loading.get_auth_plugin_conf_options('password'))),
        ('service_types',
         itertools.chain(ceilometer.energy.kwapi.SERVICE_OPTS,
                         ceilometer.image.glance.SERVICE_OPTS,
                         ceilometer.neutron_client.SERVICE_OPTS,
                         ceilometer.nova_client.SERVICE_OPTS,
                         ceilometer.objectstore.rgw.SERVICE_OPTS,
                         ceilometer.objectstore.swift.SERVICE_OPTS,)),
        ('storage', ceilometer.dispatcher.STORAGE_OPTS),
        ('vmware', ceilometer.compute.virt.vmware.inspector.OPTS),
        ('xenapi', ceilometer.compute.virt.xenapi.inspector.OPTS),
    ]
