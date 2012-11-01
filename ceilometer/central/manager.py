# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
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

from nova import manager

from ceilometer import extension_manager
from ceilometer.openstack.common import cfg
from ceilometer.openstack.common import log
from ceilometer import publish

OPTS = [
    cfg.ListOpt('disabled_central_pollsters',
                default=[],
                help='list of central pollsters to disable',
                ),
    ]

cfg.CONF.register_opts(OPTS)

LOG = log.getLogger(__name__)

PLUGIN_NAMESPACE = 'ceilometer.poll.central'


class AgentManager(manager.Manager):

    def init_host(self):
        self.ext_manager = extension_manager.ActivatedExtensionManager(
            namespace=PLUGIN_NAMESPACE,
            disabled_names=cfg.CONF.disabled_central_pollsters,
            )
        return

    @staticmethod
    def publish_counters_from_one_pollster(ext, manager, context):
        """Used to invoke the plugins loaded by the ExtensionManager.
        """
        try:
            LOG.info('polling %s', ext.name)
            for c in ext.obj.get_counters(manager, context):
                LOG.info('COUNTER: %s', c)
                publish.publish_counter(context=context,
                                        counter=c,
                                        topic=cfg.CONF.metering_topic,
                                        secret=cfg.CONF.metering_secret,
                                        source=cfg.CONF.counter_source,
                                        )
        except Exception as err:
            LOG.warning('Continuing after error from %s: %s',
                        ext.name, err)
            LOG.exception(err)

    def periodic_tasks(self, context, raise_on_error=False):
        """Tasks to be run at a periodic interval."""
        self.ext_manager.map(self.publish_counters_from_one_pollster,
                             manager=self,
                             context=context,
                             )
        return
