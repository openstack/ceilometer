#
# Copyright 2013 Red Hat, Inc
# Copyright 2013 eNovance <licensing@enovance.com>
#
# Authors: Eoghan Glynn <eglynn@redhat.com>
#          Julien Danjou <julien@danjou.info>
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

import abc

from ceilometerclient import client as ceiloclient
from oslo_config import cfg
from oslo_log import log
from oslo_service import service as os_service
from oslo_utils import netutils
import six
from stevedore import extension

from ceilometer import alarm as ceilometer_alarm
from ceilometer.alarm import rpc as rpc_alarm
from ceilometer import coordination as coordination
from ceilometer.i18n import _
from ceilometer import messaging


OPTS = [
    cfg.IntOpt('evaluation_interval',
               default=60,
               deprecated_for_removal=True,
               help='Period of evaluation cycle, should'
                    ' be >= than configured pipeline interval for'
                    ' collection of underlying meters.',
               deprecated_opts=[cfg.DeprecatedOpt(
                   'threshold_evaluation_interval', group='alarm')]),
]

cfg.CONF.register_opts(OPTS, group='alarm')
cfg.CONF.import_opt('http_timeout', 'ceilometer.service')
cfg.CONF.import_group('service_credentials', 'ceilometer.service')

LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class AlarmService(object):

    def __init__(self):
        super(AlarmService, self).__init__()
        self._load_evaluators()
        self.api_client = None

    def _load_evaluators(self):
        self.evaluators = extension.ExtensionManager(
            namespace=ceilometer_alarm.EVALUATOR_EXTENSIONS_NAMESPACE,
            invoke_on_load=True,
            invoke_args=(rpc_alarm.RPCAlarmNotifier(),)
        )
        self.supported_evaluators = [ext.name for ext in
                                     self.evaluators.extensions]

    @property
    def _client(self):
        """Construct or reuse an authenticated API client."""
        if not self.api_client:
            auth_config = cfg.CONF.service_credentials
            creds = dict(
                os_auth_url=auth_config.os_auth_url,
                os_region_name=auth_config.os_region_name,
                os_tenant_name=auth_config.os_tenant_name,
                os_password=auth_config.os_password,
                os_username=auth_config.os_username,
                os_cacert=auth_config.os_cacert,
                os_endpoint_type=auth_config.os_endpoint_type,
                insecure=auth_config.insecure,
                timeout=cfg.CONF.http_timeout,
            )
            self.api_client = ceiloclient.get_client(2, **creds)
        return self.api_client

    def _evaluate_assigned_alarms(self):
        try:
            alarms = self._assigned_alarms()
            LOG.info(_('initiating evaluation cycle on %d alarms') %
                     len(alarms))
            for alarm in alarms:
                self._evaluate_alarm(alarm)
        except Exception:
            LOG.exception(_('alarm evaluation cycle failed'))

    def _evaluate_alarm(self, alarm):
        """Evaluate the alarms assigned to this evaluator."""
        if alarm.type not in self.supported_evaluators:
            LOG.debug('skipping alarm %s: type unsupported', alarm.alarm_id)
            return

        LOG.debug('evaluating alarm %s', alarm.alarm_id)
        try:
            self.evaluators[alarm.type].obj.evaluate(alarm)
        except Exception:
            LOG.exception(_('Failed to evaluate alarm %s'), alarm.alarm_id)

    @abc.abstractmethod
    def _assigned_alarms(self):
        pass


class AlarmEvaluationService(AlarmService, os_service.Service):

    PARTITIONING_GROUP_NAME = "alarm_evaluator"

    def __init__(self):
        super(AlarmEvaluationService, self).__init__()
        self.partition_coordinator = coordination.PartitionCoordinator()

    def start(self):
        super(AlarmEvaluationService, self).start()
        self.partition_coordinator.start()
        self.partition_coordinator.join_group(self.PARTITIONING_GROUP_NAME)

        # allow time for coordination if necessary
        delay_start = self.partition_coordinator.is_active()

        if self.evaluators:
            interval = cfg.CONF.alarm.evaluation_interval
            self.tg.add_timer(
                interval,
                self._evaluate_assigned_alarms,
                initial_delay=interval if delay_start else None)
        if self.partition_coordinator.is_active():
            heartbeat_interval = min(cfg.CONF.coordination.heartbeat,
                                     cfg.CONF.alarm.evaluation_interval / 4)
            self.tg.add_timer(heartbeat_interval,
                              self.partition_coordinator.heartbeat)
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def _assigned_alarms(self):
        all_alarms = self._client.alarms.list(q=[{'field': 'enabled',
                                                  'value': True}])
        return self.partition_coordinator.extract_my_subset(
            self.PARTITIONING_GROUP_NAME, all_alarms)


class AlarmNotifierService(os_service.Service):

    def __init__(self):
        super(AlarmNotifierService, self).__init__()
        transport = messaging.get_transport()
        self.rpc_server = messaging.get_rpc_server(
            transport, cfg.CONF.alarm.notifier_rpc_topic, self)

    def start(self):
        super(AlarmNotifierService, self).start()
        self.rpc_server.start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

    def stop(self):
        self.rpc_server.stop()
        super(AlarmNotifierService, self).stop()

    def _handle_action(self, action, alarm_id, alarm_name, severity,
                       previous, current, reason, reason_data):
        try:
            action = netutils.urlsplit(action)
        except Exception:
            LOG.error(
                _("Unable to parse action %(action)s for alarm %(alarm_id)s"),
                {'action': action, 'alarm_id': alarm_id})
            return

        try:
            notifier = ceilometer_alarm.NOTIFIERS[action.scheme].obj
        except KeyError:
            scheme = action.scheme
            LOG.error(
                _("Action %(scheme)s for alarm %(alarm_id)s is unknown, "
                  "cannot notify"),
                {'scheme': scheme, 'alarm_id': alarm_id})
            return

        try:
            LOG.debug("Notifying alarm %(id)s with action %(act)s",
                      {'id': alarm_id, 'act': action})
            notifier.notify(action, alarm_id, alarm_name, severity,
                            previous, current, reason, reason_data)
        except Exception:
            LOG.exception(_("Unable to notify alarm %s"), alarm_id)
            return

    def notify_alarm(self, context, data):
        """Notify that alarm has been triggered.

           :param context: Request context.
           :param data: (dict):

             - actions, the URL of the action to run; this is mapped to
               extensions automatically
             - alarm_id, the ID of the alarm that has been triggered
             - alarm_name, the name of the alarm that has been triggered
             - severity, the level of the alarm that has been triggered
             - previous, the previous state of the alarm
             - current, the new state the alarm has transitioned to
             - reason, the reason the alarm changed its state
             - reason_data, a dict representation of the reason
        """
        actions = data.get('actions')
        if not actions:
            LOG.error(_("Unable to notify for an alarm with no action"))
            return

        for action in actions:
            self._handle_action(action,
                                data.get('alarm_id'),
                                data.get('alarm_name'),
                                data.get('severity'),
                                data.get('previous'),
                                data.get('current'),
                                data.get('reason'),
                                data.get('reason_data'))
