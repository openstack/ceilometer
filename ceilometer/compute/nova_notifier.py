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

from ceilometer.openstack.common import cfg
from ceilometer.openstack.common import log as logging

from nova import db
from ceilometer.compute.manager import AgentManager

# This module runs inside the nova compute
# agent, which only configures the "nova" logger.
# We use a fake logger name in that namespace
# so that messages from this module appear
# in the log file.
LOG = logging.getLogger('nova.ceilometer.notifier')

# NOTE(dhellmann): The _initialize_config_options is set by the tests
# to disable the cfg.CONF() call in notify(), since initializing the
# object in one tests breaks other tests unpredictably when new
# modules are imported and new options registered.
#
# GLOBAL STATE IS A BAD IDEA BUT IMPORT SIDE-EFFECTS ARE WORSE!
_initialize_config_options = True
_agent_manager = None


def initialize_manager():
    global _agent_manager
    # NOTE(dhellmann): See note above.
    if _initialize_config_options:
        cfg.CONF(args=[], project='ceilometer', prog='ceilometer-agent')
    # Instantiate a manager
    _agent_manager = AgentManager()
    _agent_manager.init_host()


def notify(context, message):
    global _agent_manager
    # Initialize the global config object as though it was in the
    # compute agent process so that the ceilometer copy of the rpc
    # modules will know how to communicate.
    if _agent_manager is None:
        initialize_manager()

    if message['event_type'] == 'compute.instance.delete.start':
        instance_id = message['payload']['instance_id']
        LOG.debug('polling final stats for %r', instance_id)
        _agent_manager.poll_instance(
            context,
            db.instance_get_by_uuid(context, instance_id))
    return
