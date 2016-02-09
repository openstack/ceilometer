#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

from oslo_config import cfg
import oslo_messaging

from ceilometer.agent import plugin_base
from ceilometer import sample

OPTS = [
    cfg.StrOpt('neutron_control_exchange',
               default='neutron',
               help="Exchange name for Neutron notifications."),
]

cfg.CONF.register_opts(OPTS)


class NetworkNotificationBase(plugin_base.NotificationBase):

    resource_name = None

    @property
    def event_types(self):
        return [
            # NOTE(flwang): When the *.create.start notification sending,
            # there is no resource id assigned by Neutron yet. So we ignore
            # the *.create.start notification for now and only listen the
            # *.create.end to make sure the resource id is existed.
            '%s.create.end' % self.resource_name,
            '%s.update.*' % self.resource_name,
            '%s.exists' % self.resource_name,
            # FIXME(dhellmann): Neutron delete notifications do
            # not include the same metadata as the other messages,
            # so we ignore them for now. This isn't ideal, since
            # it may mean we miss charging for some amount of time,
            # but it is better than throwing away the existing
            # metadata for a resource when it is deleted.
            # '%s.delete.start' % (self.resource_name),
        ]

    def get_targets(self, conf):
        """Return a sequence of oslo_messaging.Target

        This sequence is defining the exchange and topics to be connected for
        this plugin.
        """
        return [oslo_messaging.Target(topic=topic,
                                      exchange=conf.neutron_control_exchange)
                for topic in self.get_notification_topics(conf)]

    def process_notification(self, message):
        counter_name = getattr(self, 'counter_name', self.resource_name)
        unit_value = getattr(self, 'unit', self.resource_name)

        resource = message['payload'].get(self.resource_name)
        if resource:
            # NOTE(liusheng): In %s.update.start notifications, the id is in
            # message['payload'] instead of resource itself.
            if message['event_type'].endswith('update.start'):
                resource['id'] = message['payload']['id']
            resources = [resource]
        else:
            resources = message['payload'].get(self.resource_name + 's', [])

        resource_message = message.copy()
        for resource in resources:
            resource_message['payload'] = resource
            yield sample.Sample.from_notification(
                name=counter_name,
                type=sample.TYPE_GAUGE,
                unit=unit_value,
                volume=1,
                user_id=resource_message['_context_user_id'],
                project_id=resource_message['_context_tenant_id'],
                resource_id=resource['id'],
                message=resource_message)
            event_type_split = resource_message['event_type'].split('.')
            if len(event_type_split) > 2:
                yield sample.Sample.from_notification(
                    name=counter_name
                    + "." + event_type_split[1],
                    type=sample.TYPE_DELTA,
                    unit=unit_value,
                    volume=1,
                    user_id=resource_message['_context_user_id'],
                    project_id=resource_message['_context_tenant_id'],
                    resource_id=resource['id'],
                    message=resource_message)


class Network(NetworkNotificationBase, plugin_base.NonMetricNotificationBase):
    """Listen for Neutron network notifications.

    Handle network.{create.end|update.*|exists} notifications from neutron.
    """
    resource_name = 'network'


class Subnet(NetworkNotificationBase, plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle subnet.{create.end|update.*|exists} notifications from neutron.
    """
    resource_name = 'subnet'


class Port(NetworkNotificationBase, plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle port.{create.end|update.*|exists} notifications from neutron.
    """
    resource_name = 'port'


class Router(NetworkNotificationBase, plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle router.{create.end|update.*|exists} notifications from neutron.
    """
    resource_name = 'router'


class FloatingIP(NetworkNotificationBase,
                 plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle floatingip.{create.end|update.*|exists} notifications from neutron.
    """
    resource_name = 'floatingip'
    counter_name = 'ip.floating'
    unit = 'ip'


class Pool(NetworkNotificationBase, plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle pool.{create.end|update.*|exists} notifications from neutron.
    """
    resource_name = 'pool'
    counter_name = 'network.services.lb.pool'


class Vip(NetworkNotificationBase, plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle vip.{create.end|update.*|exists} notifications from neutron.
    """
    resource_name = 'vip'
    counter_name = 'network.services.lb.vip'


class Member(NetworkNotificationBase, plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle member.{create.end|update.*|exists} notifications from neutron.
    """
    resource_name = 'member'
    counter_name = 'network.services.lb.member'


class HealthMonitor(NetworkNotificationBase,
                    plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle health_monitor.{create.end|update.*|exists} notifications
    from neutron.
    """
    resource_name = 'health_monitor'
    counter_name = 'network.services.lb.health_monitor'


class Firewall(NetworkNotificationBase, plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle firewall.{create.end|update.*|exists} notifications from neutron.
    """
    resource_name = 'firewall'
    counter_name = 'network.services.firewall'


class FirewallPolicy(NetworkNotificationBase,
                     plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle firewall_policy.{create.end|update.*|exists} notifications
    from neutron.
    """
    resource_name = 'firewall_policy'
    counter_name = 'network.services.firewall.policy'


class FirewallRule(NetworkNotificationBase,
                   plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle firewall_rule.{create.end|update.*|exists} notifications
    from neutron.
    """
    resource_name = 'firewall_rule'
    counter_name = 'network.services.firewall.rule'


class VPNService(NetworkNotificationBase,
                 plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle vpnservice.{create.end|update.*|exists} notifications from neutron.
    """
    resource_name = 'vpnservice'
    counter_name = 'network.services.vpn'


class IPSecPolicy(NetworkNotificationBase,
                  plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle pool.{create.end|update.*|exists} notifications from neutron.
    """
    resource_name = 'ipsecpolicy'
    counter_name = 'network.services.vpn.ipsecpolicy'


class IKEPolicy(NetworkNotificationBase,
                plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle ikepolicy.{create.end|update.*|exists} notifications from neutron.
    """
    resource_name = 'ikepolicy'
    counter_name = 'network.services.vpn.ikepolicy'


class IPSecSiteConnection(NetworkNotificationBase,
                          plugin_base.NonMetricNotificationBase):
    """Listen for Neutron notifications.

    Handle ipsec_site_connection.{create.end|update.*|exists}
    notifications from neutron.
    """
    resource_name = 'ipsec_site_connection'
    counter_name = 'network.services.vpn.connections'
