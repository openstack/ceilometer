# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
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
"""Storage backend management
"""

from stevedore import driver

from ceilometer.openstack.common import log
from ceilometer.openstack.common import cfg

from urlparse import urlparse

LOG = log.getLogger(__name__)

STORAGE_ENGINE_NAMESPACE = 'ceilometer.storage'

STORAGE_OPTS = [
    cfg.StrOpt('database_connection',
               default='mongodb://localhost:27017/ceilometer',
               help='Database connection string',
               ),
    ]


cfg.CONF.register_opts(STORAGE_OPTS)


def register_opts(conf):
    """Register any options for the storage system.
    """
    p = get_engine(conf)
    p.register_opts(conf)


def get_engine(conf):
    """Load the configured engine and return an instance.
    """
    engine_name = urlparse(conf.database_connection).scheme
    LOG.debug('looking for %r driver in %r',
              engine_name, STORAGE_ENGINE_NAMESPACE)
    mgr = driver.DriverManager(STORAGE_ENGINE_NAMESPACE,
                               engine_name,
                               invoke_on_load=True)
    return mgr.driver


def get_connection(conf):
    """Return an open connection to the database.
    """
    engine = get_engine(conf)
    engine.register_opts(conf)
    db = engine.get_connection(conf)
    return db


class EventFilter(object):
    """Holds the properties for building a query to filter events.

    :param user: The event owner.
    :param project: The event owner.
    :param start: Earliest timestamp to include.
    :param end: Only include events with timestamp less than this.
    :param resource: Optional filter for resource id.
    :param meter: Optional filter for meter type using the meter name.
    :param source: Optional source filter.
    """
    def __init__(self, user=None, project=None, start=None, end=None,
                 resource=None, meter=None, source=None):
        self.user = user
        self.project = project
        self.start = start
        self.end = end
        self.resource = resource
        self.meter = meter
        self.source = source
