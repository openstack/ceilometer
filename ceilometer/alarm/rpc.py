# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
#
# Authors: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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

from oslo.config import cfg

from ceilometer.openstack.common import context
from ceilometer.openstack.common.rpc import proxy as rpc_proxy
from ceilometer.storage.models import Alarm

OPTS = [
    cfg.StrOpt('notifier_rpc_topic',
               default='alarm_notifier',
               help='the topic ceilometer uses for alarm notifier messages'),
    cfg.StrOpt('partition_rpc_topic',
               default='alarm_partition_coordination',
               help='the topic ceilometer uses for alarm partition '
                    'coordination messages'),
]

cfg.CONF.register_opts(OPTS, group='alarm')


class RPCAlarmNotifier(rpc_proxy.RpcProxy):
    def __init__(self):
        super(RPCAlarmNotifier, self).__init__(
            default_version='1.0',
            topic=cfg.CONF.alarm.notifier_rpc_topic)

    def notify(self, alarm, previous, reason):
        actions = getattr(alarm, Alarm.ALARM_ACTIONS_MAP[alarm.state])
        msg = self.make_msg('notify_alarm', data={
            'actions': actions,
            'alarm_id': alarm.alarm_id,
            'previous': previous,
            'current': alarm.state,
            'reason': reason})
        self.cast(context.get_admin_context(), msg)


class RPCAlarmPartitionCoordination(rpc_proxy.RpcProxy):
    def __init__(self):
        super(RPCAlarmPartitionCoordination, self).__init__(
            default_version='1.0',
            topic=cfg.CONF.alarm.partition_rpc_topic)

    def presence(self, uuid, priority):
        msg = self.make_msg('presence', data={
            'uuid': uuid,
            'priority': priority})
        self.fanout_cast(context.get_admin_context(), msg)

    def assign(self, uuid, alarms):
        msg = self.make_msg('assign', data={
            'uuid': uuid,
            'alarms': alarms})
        return self.fanout_cast(context.get_admin_context(), msg)

    def allocate(self, uuid, alarms):
        msg = self.make_msg('allocate', data={
            'uuid': uuid,
            'alarms': alarms})
        return self.fanout_cast(context.get_admin_context(), msg)
