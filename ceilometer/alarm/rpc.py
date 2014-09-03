#
# Copyright 2013 eNovance <licensing@enovance.com>
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
import six

from ceilometer.alarm.storage import models
from ceilometer import messaging
from ceilometer.openstack.common import context
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log

OPTS = [
    cfg.StrOpt('notifier_rpc_topic',
               default='alarm_notifier',
               help='The topic that ceilometer uses for alarm notifier '
                    'messages.'),
    cfg.StrOpt('partition_rpc_topic',
               default='alarm_partition_coordination',
               help='The topic that ceilometer uses for alarm partition '
                    'coordination messages. DEPRECATED: RPC-based partitioned'
                    'alarm evaluation service will be removed in Kilo in '
                    'favour of the default alarm evaluation service using '
                    'tooz for partitioning.'),
]

cfg.CONF.register_opts(OPTS, group='alarm')

LOG = log.getLogger(__name__)


class RPCAlarmNotifier(object):
    def __init__(self):
        transport = messaging.get_transport()
        self.client = messaging.get_rpc_client(
            transport, topic=cfg.CONF.alarm.notifier_rpc_topic,
            version="1.0")

    def notify(self, alarm, previous, reason, reason_data):
        actions = getattr(alarm, models.Alarm.ALARM_ACTIONS_MAP[alarm.state])
        if not actions:
            LOG.debug(_('alarm %(alarm_id)s has no action configured '
                        'for state transition from %(previous)s to '
                        'state %(state)s, skipping the notification.') %
                      {'alarm_id': alarm.alarm_id,
                       'previous': previous,
                       'state': alarm.state})
            return
        self.client.cast(context.get_admin_context(),
                         'notify_alarm', data={
                             'actions': actions,
                             'alarm_id': alarm.alarm_id,
                             'previous': previous,
                             'current': alarm.state,
                             'reason': six.text_type(reason),
                             'reason_data': reason_data})


class RPCAlarmPartitionCoordination(object):
    def __init__(self):
        transport = messaging.get_transport()
        self.client = messaging.get_rpc_client(
            transport, topic=cfg.CONF.alarm.partition_rpc_topic,
            version="1.0")

    def presence(self, uuid, priority):
        cctxt = self.client.prepare(fanout=True)
        return cctxt.cast(context.get_admin_context(),
                          'presence', data={'uuid': uuid,
                                            'priority': priority})

    def assign(self, uuid, alarms):
        cctxt = self.client.prepare(fanout=True)
        return cctxt.cast(context.get_admin_context(),
                          'assign', data={'uuid': uuid,
                                          'alarms': alarms})

    def allocate(self, uuid, alarms):
        cctxt = self.client.prepare(fanout=True)
        return cctxt.cast(context.get_admin_context(),
                          'allocate', data={'uuid': uuid,
                                            'alarms': alarms})
