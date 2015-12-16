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

from ceilometer.i18n import _LW


LOG = log.getLogger(__name__)

OPTS = [
    cfg.MultiStrOpt('meter_dispatchers',
                    deprecated_name='dispatcher',
                    default=['database'],
                    help='Dispatchers to process metering data.'),
    cfg.MultiStrOpt('event_dispatchers',
                    default=['database'],
                    deprecated_name='dispatcher',
                    help='Dispatchers to process event data.'),
]
cfg.CONF.register_opts(OPTS)

STORAGE_OPTS = [
    cfg.IntOpt('max_retries',
               default=10,
               deprecated_group='database',
               help='Maximum number of connection retries during startup. '
                    'Set to -1 to specify an infinite retry count.'),
    cfg.IntOpt('retry_interval',
               default=10,
               deprecated_group='database',
               help='Interval (in seconds) between retries of connection.'),
]
cfg.CONF.register_opts(STORAGE_OPTS, group='storage')


def _load_dispatcher_manager(dispatcher_type):
    namespace = 'ceilometer.dispatcher.%s' % dispatcher_type
    conf_name = '%s_dispatchers' % dispatcher_type

    LOG.debug('loading dispatchers from %s', namespace)
    # set propagate_map_exceptions to True to enable stevedore
    # to propagate exceptions.
    dispatcher_manager = named.NamedExtensionManager(
        namespace=namespace,
        names=getattr(cfg.CONF, conf_name),
        invoke_on_load=True,
        invoke_args=[cfg.CONF],
        propagate_map_exceptions=True)
    if not list(dispatcher_manager):
        LOG.warning(_LW('Failed to load any dispatchers for %s'),
                    namespace)
    return dispatcher_manager


def load_dispatcher_manager():
    return (_load_dispatcher_manager('meter'),
            _load_dispatcher_manager('event'))


class Base(object):
    def __init__(self, conf):
        self.conf = conf


@six.add_metaclass(abc.ABCMeta)
class MeterDispatcherBase(Base):
    @abc.abstractmethod
    def record_metering_data(self, data):
        """Recording metering data interface."""


@six.add_metaclass(abc.ABCMeta)
class EventDispatcherBase(Base):
    @abc.abstractmethod
    def record_events(self, events):
        """Recording events interface."""
