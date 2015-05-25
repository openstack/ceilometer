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
"""DB2 storage backend
"""
import pymongo

from ceilometer.event.storage import pymongo_base
from ceilometer import storage
from ceilometer.storage.mongo import utils as pymongo_utils


class Connection(pymongo_base.Connection):
    """The db2 event storage for Ceilometer."""

    CONNECTION_POOL = pymongo_utils.ConnectionPool()

    def __init__(self, url):

        # Since we are using pymongo, even though we are connecting to DB2
        # we still have to make sure that the scheme which used to distinguish
        # db2 driver from mongodb driver be replaced so that pymongo will not
        # produce an exception on the scheme.
        url = url.replace('db2:', 'mongodb:', 1)
        self.conn = self.CONNECTION_POOL.connect(url)

        # Require MongoDB 2.2 to use aggregate(), since we are using mongodb
        # as backend for test, the following code is necessary to make sure
        # that the test wont try aggregate on older mongodb during the test.
        # For db2, the versionArray won't be part of the server_info, so there
        # will not be exception when real db2 gets used as backend.
        server_info = self.conn.server_info()
        if server_info.get('sysInfo'):
            self._using_mongodb = True
        else:
            self._using_mongodb = False

        if self._using_mongodb and server_info.get('versionArray') < [2, 2]:
            raise storage.StorageBadVersion("Need at least MongoDB 2.2")

        connection_options = pymongo.uri_parser.parse_uri(url)
        self.db = getattr(self.conn, connection_options['database'])
        if connection_options.get('username'):
            self.db.authenticate(connection_options['username'],
                                 connection_options['password'])

        self.upgrade()

    def upgrade(self):
        # create collection if not present
        if 'event' not in self.db.conn.collection_names():
            self.db.conn.create_collection('event')

    def clear(self):
        # drop_database command does nothing on db2 database since this has
        # not been implemented. However calling this method is important for
        # removal of all the empty dbs created during the test runs since
        # test run is against mongodb on Jenkins
        self.conn.drop_database(self.db.name)
        self.conn.close()
