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

__all__ = [
    'notify',
    'initialize_manager',
]

from nova import db as instance_info_source
from oslo.config import cfg

from ceilometer.compute import manager as compute_manager
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log as logging

# This module runs inside the nova compute
# agent, which only configures the "nova" logger.
# We use a fake logger name in that namespace
# so that messages from this module appear
# in the log file.
LOG = logging.getLogger('nova.ceilometer.notifier')

_agent_manager = None


def initialize_manager(agent_manager=None):
    global _agent_manager
    if not agent_manager:
        cfg.CONF(args=[], project='ceilometer', prog='ceilometer-agent')
        # Instantiate a manager
        _agent_manager = compute_manager.AgentManager()
    else:
        _agent_manager = agent_manager
    _agent_manager.setup_notifier_task()


def notify(context, message):
    global _agent_manager
    # Initialize the global config object as though it was in the
    # compute agent process so that the ceilometer copy of the rpc
    # modules will know how to communicate.
    if _agent_manager is None:
        initialize_manager()

    if message['event_type'] == 'compute.instance.delete.start':
        instance_id = message['payload']['instance_id']
        LOG.debug(_('polling final stats for %r'), instance_id)
        _agent_manager.poll_instance(context,
                                     instance_info_source.instance_get_by_uuid(
                                         context,
                                         instance_id))
