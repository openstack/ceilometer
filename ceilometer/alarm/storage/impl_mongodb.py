#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 eNovance
# Copyright 2014 Red Hat, Inc
#
# Authors: Doug Hellmann <doug.hellmann@dreamhost.com>
#          Julien Danjou <julien@danjou.info>
#          Eoghan Glynn <eglynn@redhat.com>
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
"""MongoDB storage backend"""

from oslo.config import cfg
import pymongo

from ceilometer.alarm.storage import pymongo_base
from ceilometer.openstack.common import log
from ceilometer import storage
from ceilometer.storage.mongo import utils as pymongo_utils

cfg.CONF.import_opt('time_to_live', 'ceilometer.storage',
                    group="database")

LOG = log.getLogger(__name__)


class Connection(pymongo_base.Connection):
    """Put the alarm data into a MongoDB database."""

    CONNECTION_POOL = pymongo_utils.ConnectionPool()

    def __init__(self, url):

        # NOTE(jd) Use our own connection pooling on top of the Pymongo one.
        # We need that otherwise we overflow the MongoDB instance with new
        # connection since we instanciate a Pymongo client each time someone
        # requires a new storage connection.
        self.conn = self.CONNECTION_POOL.connect(url)

        # Require MongoDB 2.4 to use $setOnInsert
        if self.conn.server_info()['versionArray'] < [2, 4]:
            raise storage.StorageBadVersion("Need at least MongoDB 2.4")

        connection_options = pymongo.uri_parser.parse_uri(url)
        self.db = getattr(self.conn, connection_options['database'])
        if connection_options.get('username'):
            self.db.authenticate(connection_options['username'],
                                 connection_options['password'])

        # NOTE(jd) Upgrading is just about creating index, so let's do this
        # on connection to be sure at least the TTL is correcly updated if
        # needed.
        self.upgrade()

    def clear(self):
        self.conn.drop_database(self.db)
        # Connection will be reopened automatically if needed
        self.conn.close()
