# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
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
"""Handler for producing network counter messages from Neutron notification
   events.

"""
import copy

from oslo.config import cfg

from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer import plugin
from ceilometer import sample

OPTS = [
    cfg.StrOpt('neutron_control_exchange',
               default='neutron',
               help="Exchange name for Neutron notifications.",
               deprecated_name='quantum_control_exchange'),
]

cfg.CONF.register_opts(OPTS)

LOG = log.getLogger(__name__)


class NetworkNotificationBase(plugin.NotificationBase):

    resource_name = None

    @property
    def event_types(self):
        return [
            # NOTE(flwang): When the *.create.start notification sending,
            # there is no resource id assigned by Neutron yet. So we ignore
            # the *.create.start notification for now and only listen the
            # *.create.end to make sure the resource id is existed.
            '%s.create.end' % (self.resource_name),
            '%s.update.*' % (self.resource_name),
            '%s.exists' % (self.resource_name),
            # FIXME(dhellmann): Neutron delete notifications do
            # not include the same metadata as the other messages,
            # so we ignore them for now. This isn't ideal, since
            # it may mean we miss charging for some amount of time,
            # but it is better than throwing away the existing
            # metadata for a resource when it is deleted.
            ##'%s.delete.start' % (self.resource_name),
        ]

    @staticmethod
    def get_exchange_topics(conf):
        """Return a sequence of ExchangeTopics defining the exchange and topics
        to be connected for this plugin.

        """
        return [
            plugin.ExchangeTopics(
                exchange=conf.neutron_control_exchange,
                topics=set(topic + ".info"
                           for topic in conf.notification_topics)),
        ]

    def process_notification(self, message):
        LOG.info(_('network notification %r') % message)
        counter_name = getattr(self, 'counter_name', self.resource_name)
        unit_value = getattr(self, 'unit', self.resource_name)

        payload = message['payload'].get(self.resource_name)
        payloads = message['payload'].get(self.resource_name + 's')
        payload_list = copy.copy([payload] if payload else payloads)
        for p in payload_list:
            message['payload'] = p
            yield sample.Sample.from_notification(
                name=counter_name,
                type=sample.TYPE_GAUGE,
                unit=unit_value,
                volume=1,
                user_id=message['_context_user_id'],
                project_id=message['_context_tenant_id'],
                resource_id=message['payload']['id'],
                message=message)
            event_type_split = message['event_type'].split('.')
            if len(event_type_split) > 2:
                yield sample.Sample.from_notification(
                    name=counter_name
                    + "." + event_type_split[1],
                    type=sample.TYPE_DELTA,
                    unit=unit_value,
                    volume=1,
                    user_id=message['_context_user_id'],
                    project_id=message['_context_tenant_id'],
                    resource_id=message['payload']['id'],
                    message=message)


class Network(NetworkNotificationBase):
    """Listen for Neutron network notifications in order to mediate with the
    metering framework.

    """
    resource_name = 'network'


class Subnet(NetworkNotificationBase):
    """Listen for Neutron notifications in order to mediate with the
    metering framework.

    """
    resource_name = 'subnet'


class Port(NetworkNotificationBase):
    """Listen for Neutron notifications in order to mediate with the
    metering framework.

    """
    resource_name = 'port'


class Router(NetworkNotificationBase):
    """Listen for Neutron notifications in order to mediate with the
    metering framework.

    """
    resource_name = 'router'


class FloatingIP(NetworkNotificationBase):
    """Listen for Neutron notifications in order to mediate with the
    metering framework.

    """
    resource_name = 'floatingip'
    counter_name = 'ip.floating'
    unit = 'ip'


class Bandwidth(NetworkNotificationBase):
    """Listen for Neutron notifications in order to mediate with the
    metering framework.

    """
    event_types = ['l3.meter']

    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name='bandwidth',
            type=sample.TYPE_DELTA,
            unit='B',
            volume=message['payload']['bytes'],
            user_id=None,
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['label_id'],
            message=message)
