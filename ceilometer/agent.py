# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Julien Danjou
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

from stevedore import dispatch
from ceilometer.openstack.common import cfg
from ceilometer.openstack.common import log
from ceilometer import pipeline

LOG = log.getLogger(__name__)


class AgentManager(object):

    def __init__(self, extension_manager):
        publisher_manager = dispatch.NameDispatchExtensionManager(
            namespace=pipeline.PUBLISHER_NAMESPACE,
            check_func=lambda x: True,
            invoke_on_load=True,
        )

        self.pipeline_manager = pipeline.setup_pipeline(publisher_manager)

        self.pollster_manager = extension_manager

    def publish_counters_from_one_pollster(self, ext, manager, context,
                                           *args, **kwargs):
        """Used to invoke the plugins loaded by the ExtensionManager.
        """
        try:
            LOG.info('Polling %s', ext.name)
            for c in ext.obj.get_counters(manager, *args, **kwargs):
                LOG.debug('Publishing counter: %s', c)
                manager.pipeline_manager.publish_counter(
                    context, c,
                    cfg.CONF.counter_source)

        except Exception as err:
            LOG.warning('Continuing after error from %s: %s',
                        ext.name, err)
            LOG.exception(err)
