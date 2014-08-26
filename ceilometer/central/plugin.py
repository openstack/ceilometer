#
# Copyright 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Base class for plugins used by the central agent.
"""

from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer import plugin

LOG = log.getLogger(__name__)


class CentralPollster(plugin.PollsterBase):
    """Base class for plugins that support the polling API."""


def check_keystone(service_type=None, client=None):
    """Decorator function to check if manager has valid keystone client.

       Also checks if the service is registered/enabled in Keystone.

       :param service_type: name of service in Keystone
       :param client: client name if not passed in as function param
    """
    def wrapped(f):
        def func(self, *args, **kwargs):
            if client:
                manager = getattr(self, client, None)
            else:
                manager = kwargs.get('manager')
            if not manager and len(args) > 0:
                manager = args[0]
            keystone = getattr(manager, 'keystone', None)
            if not keystone or isinstance(keystone, Exception):
                LOG.error(_('Skip due to keystone error %s'),
                          str(keystone) if keystone else '')
                return iter([])
            elif service_type:
                endpoints = keystone.service_catalog.get_endpoints()
                if not endpoints.get(service_type):
                    LOG.warning(_('Skipping because service is not'
                                  'registered in keystone'))
                    return iter([])
            return f(self, *args, **kwargs)
        return func
    return wrapped
