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

import ceilometer.agent.manager
import ceilometer.alarm.notifier.rest
import ceilometer.alarm.rpc
import ceilometer.alarm.service
import ceilometer.api
import ceilometer.api.app
import ceilometer.api.controllers.v2
import ceilometer.cmd.alarm
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
import ceilometer.data_processing.notifications
import ceilometer.dispatcher
import ceilometer.dispatcher.file
import ceilometer.energy.kwapi
import ceilometer.event.converter
import ceilometer.hardware.discovery
import ceilometer.identity.notifications
import ceilometer.image.glance
import ceilometer.image.notifications
import ceilometer.ipmi.notifications.ironic
import ceilometer.ipmi.platform.intel_node_manager
import ceilometer.middleware
import ceilometer.network.notifications
import ceilometer.neutron_client
import ceilometer.notification
import ceilometer.nova_client
import ceilometer.objectstore.swift
import ceilometer.openstack.common.eventlet_backdoor
import ceilometer.openstack.common.log
import ceilometer.openstack.common.policy
import ceilometer.orchestration.notifications
import ceilometer.pipeline
import ceilometer.profiler.notifications
import ceilometer.publisher.messaging
import ceilometer.publisher.utils
import ceilometer.sample
import ceilometer.service
import ceilometer.storage
import ceilometer.utils
import ceilometer.volume.notifications


def list_opts():
    return [
        ('DEFAULT',
         itertools.chain(ceilometer.agent.base.OPTS,
                         ceilometer.api.app.OPTS,
                         ceilometer.cmd.polling.CLI_OPTS,
                         ceilometer.compute.notifications.OPTS,
                         ceilometer.compute.util.OPTS,
                         ceilometer.compute.virt.inspector.OPTS,
                         ceilometer.compute.virt.libvirt.inspector.OPTS,
                         ceilometer.data_processing.notifications.OPTS,
                         ceilometer.dispatcher.OPTS,
                         ceilometer.identity.notifications.OPTS,
                         ceilometer.image.glance.OPTS,
                         ceilometer.image.notifications.OPTS,
                         ceilometer.ipmi.notifications.ironic.OPTS,
                         ceilometer.middleware.OPTS,
                         ceilometer.network.notifications.OPTS,
                         ceilometer.nova_client.OPTS,
                         ceilometer.objectstore.swift.OPTS,
                         (ceilometer.openstack.common.eventlet_backdoor
                          .eventlet_backdoor_opts),
                         ceilometer.openstack.common.log.common_cli_opts,
                         ceilometer.openstack.common.log.generic_log_opts,
                         ceilometer.openstack.common.log.logging_cli_opts,
                         ceilometer.openstack.common.log.log_opts,
                         ceilometer.openstack.common.policy.policy_opts,
                         ceilometer.orchestration.notifications.OPTS,
                         ceilometer.pipeline.OPTS,
                         ceilometer.profiler.notifications.OPTS,
                         ceilometer.sample.OPTS,
                         ceilometer.service.OPTS,
                         ceilometer.storage.OLD_OPTS,
                         ceilometer.utils.OPTS,
                         ceilometer.volume.notifications.OPTS,)),
        ('alarm',
         itertools.chain(ceilometer.alarm.notifier.rest.OPTS,
                         ceilometer.alarm.service.OPTS,
                         ceilometer.alarm.rpc.OPTS,
                         ceilometer.api.controllers.v2.ALARM_API_OPTS,
                         ceilometer.cmd.alarm.OPTS)),
        ('api',
         itertools.chain(ceilometer.api.OPTS,
                         ceilometer.api.app.API_OPTS,)),
        # deprecated path, new one is 'polling'
        ('central', ceilometer.agent.manager.OPTS),
        ('collector', ceilometer.collector.OPTS),
        ('compute', ceilometer.compute.discovery.OPTS),
        ('coordination', ceilometer.coordination.OPTS),
        ('database', ceilometer.storage.OPTS),
        ('dispatcher_file', ceilometer.dispatcher.file.OPTS),
        ('event', ceilometer.event.converter.OPTS),
        ('hardware', ceilometer.hardware.discovery.OPTS),
        ('ipmi', ceilometer.ipmi.platform.intel_node_manager.OPTS),
        ('notification', ceilometer.notification.OPTS),
        ('polling', ceilometer.agent.manager.OPTS),
        ('publisher', ceilometer.publisher.utils.OPTS),
        ('publisher_notifier', ceilometer.publisher.messaging.NOTIFIER_OPTS),
        ('publisher_rpc', ceilometer.publisher.messaging.RPC_OPTS),
        ('service_credentials', ceilometer.service.CLI_OPTS),
        ('service_types',
         itertools.chain(ceilometer.energy.kwapi.SERVICE_OPTS,
                         ceilometer.image.glance.SERVICE_OPTS,
                         ceilometer.neutron_client.SERVICE_OPTS,
                         ceilometer.nova_client.SERVICE_OPTS,
                         ceilometer.objectstore.swift.SERVICE_OPTS,)),
        ('vmware', ceilometer.compute.virt.vmware.inspector.OPTS),
        ('xenapi', ceilometer.compute.virt.xenapi.inspector.OPTS),
    ]
