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
"""In-memory storage driver for use with tests.

This driver is based on MIM, an in-memory version of MongoDB.
"""

from ming import mim

from ceilometer.openstack.common import log as logging

from ceilometer.storage import base
from ceilometer.storage import impl_mongodb


LOG = logging.getLogger(__name__)


class TestDBStorage(base.StorageEngine):
    """Put the data into an in-memory database for testing

    This driver is based on MIM, an in-memory version of MongoDB.

    Collections::

        - user
          - { _id: user id
              source: [ array of source ids reporting for the user ]
              }
        - project
          - { _id: project id
              source: [ array of source ids reporting for the project ]
              }
        - meter
          - the raw incoming data
        - resource
          - the metadata for resources
          - { _id: uuid of resource,
              metadata: metadata dictionaries
              timestamp: datetime of last update
              user_id: uuid
              project_id: uuid
              meter: [ array of {counter_name: string, counter_type: string,
                                 counter_unit: string} ]
            }
    """

    OPTIONS = []

    def register_opts(self, conf):
        """Register any configuration options used by this engine.
        """
        conf.register_opts(self.OPTIONS)

    def get_connection(self, conf):
        """Return a Connection instance based on the configuration settings.
        """
        return TestConnection(conf)


class TestConnection(impl_mongodb.Connection):

    _mim_instance = None

    def _get_connection(self, conf):
        # MIM will die if we have too many connections, so use a
        # Singleton
        if TestConnection._mim_instance is None:
            LOG.debug('Creating a new MIM Connection object')
            TestConnection._mim_instance = mim.Connection()
        return TestConnection._mim_instance
