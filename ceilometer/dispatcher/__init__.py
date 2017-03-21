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


LOG = log.getLogger(__name__)

OPTS = [
    cfg.MultiStrOpt('meter_dispatchers',
                    deprecated_name='dispatcher',
                    default=[],
                    deprecated_for_removal=True,
                    deprecated_reason='This option only be used in collector '
                                      'service, the collector service has '
                                      'been deprecated and will be removed '
                                      'in the future, this should also be '
                                      'deprecated for removal with collector '
                                      'service.',
                    help='Dispatchers to process metering data.'),
    cfg.MultiStrOpt('event_dispatchers',
                    default=[],
                    deprecated_name='dispatcher',
                    deprecated_for_removal=True,
                    deprecated_reason='This option only be used in collector '
                                      'service, the collector service has '
                                      'been deprecated and will be removed '
                                      'in the future, this should also be '
                                      'deprecated for removal with collector '
                                      'service.',
                    help='Dispatchers to process event data.'),
]


def _load_dispatcher_manager(conf, dispatcher_type):
    namespace = 'ceilometer.dispatcher.%s' % dispatcher_type
    conf_name = '%s_dispatchers' % dispatcher_type

    LOG.debug('loading dispatchers from %s', namespace)
    # set propagate_map_exceptions to True to enable stevedore
    # to propagate exceptions.
    dispatcher_manager = named.NamedExtensionManager(
        namespace=namespace,
        names=getattr(conf, conf_name),
        invoke_on_load=True,
        invoke_args=[conf],
        propagate_map_exceptions=True)
    if not list(dispatcher_manager):
        LOG.warning('Failed to load any dispatchers for %s',
                    namespace)
    return dispatcher_manager


def load_dispatcher_manager(conf):
    return (_load_dispatcher_manager(conf, 'meter'),
            _load_dispatcher_manager(conf, 'event'))


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
        """Record events."""
