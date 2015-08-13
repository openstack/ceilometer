#
# Copyright 2013 IBM
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

from oslo_config import cfg
from oslo_log import log
import six
from stevedore import named

from ceilometer.i18n import _


LOG = log.getLogger(__name__)

OPTS = [
    cfg.MultiStrOpt('dispatcher',
                    deprecated_group="collector",
                    default=['database'],
                    help='Dispatcher to process data.'),
]
cfg.CONF.register_opts(OPTS)


DISPATCHER_NAMESPACE = 'ceilometer.dispatcher'


def load_dispatcher_manager():
    LOG.debug('loading dispatchers from %s', DISPATCHER_NAMESPACE)
    # set propagate_map_exceptions to True to enable stevedore
    # to propagate exceptions.
    dispatcher_manager = named.NamedExtensionManager(
        namespace=DISPATCHER_NAMESPACE,
        names=cfg.CONF.dispatcher,
        invoke_on_load=True,
        invoke_args=[cfg.CONF],
        propagate_map_exceptions=True)
    if not list(dispatcher_manager):
        LOG.warning(_('Failed to load any dispatchers for %s'),
                    DISPATCHER_NAMESPACE)
    return dispatcher_manager


@six.add_metaclass(abc.ABCMeta)
class Base(object):

    def __init__(self, conf):
        self.conf = conf

    @abc.abstractmethod
    def record_metering_data(self, data):
        """Recording metering data interface."""

    @abc.abstractmethod
    def record_events(self, events):
        """Recording events interface."""
