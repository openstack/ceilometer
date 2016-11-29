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

import os

import happybase
from oslo_log import log
from oslo_utils import netutils
from six.moves.urllib import parse as urlparse

from ceilometer.storage.hbase import inmemory as hbase_inmemory

LOG = log.getLogger(__name__)


class Connection(object):
    """Base connection class for HBase."""

    _memory_instance = None

    def __init__(self, conf, url):
        super(Connection, self).__init__(conf, url)
        """Hbase Connection Initialization."""
        opts = self._parse_connection_url(url)

        if opts['host'] == '__test__':
            url = os.environ.get('CEILOMETER_TEST_HBASE_URL')
            if url:
                # Reparse URL, but from the env variable now
                opts = self._parse_connection_url(url)
                self.conn_pool = self._get_connection_pool(opts)
            else:
                # This is a in-memory usage for unit tests
                if Connection._memory_instance is None:
                    LOG.debug('Creating a new in-memory HBase '
                              'Connection object')
                    Connection._memory_instance = (hbase_inmemory.
                                                   MConnectionPool())
                self.conn_pool = Connection._memory_instance
        else:
            self.conn_pool = self._get_connection_pool(opts)

    @staticmethod
    def _get_connection_pool(conf):
        """Return a connection pool to the database.

        .. note::

          The tests use a subclass to override this and return an
          in-memory connection pool.
        """
        LOG.debug('connecting to HBase on %(host)s:%(port)s',
                  {'host': conf['host'], 'port': conf['port']})
        return happybase.ConnectionPool(
            size=100, host=conf['host'], port=conf['port'],
            table_prefix=conf['table_prefix'],
            table_prefix_separator=conf['table_prefix_separator'])

    @staticmethod
    def _parse_connection_url(url):
        """Parse connection parameters from a database url.

        .. note::

          HBase Thrift does not support authentication and there is no
          database name, so we are not looking for these in the url.
        """
        opts = {}
        result = netutils.urlsplit(url)
        opts['table_prefix'] = urlparse.parse_qs(
            result.query).get('table_prefix', [None])[0]
        opts['table_prefix_separator'] = urlparse.parse_qs(
            result.query).get('table_prefix_separator', ['_'])[0]
        opts['dbtype'] = result.scheme
        if ':' in result.netloc:
            opts['host'], port = result.netloc.split(':')
        else:
            opts['host'] = result.netloc
            port = 9090
        opts['port'] = port and int(port) or 9090
        return opts
