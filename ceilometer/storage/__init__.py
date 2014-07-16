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
"""Storage backend management
"""

from oslo.config import cfg
import six
import six.moves.urllib.parse as urlparse
from stevedore import driver

from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer import utils


LOG = log.getLogger(__name__)

OLD_STORAGE_OPTS = [
    cfg.StrOpt('database_connection',
               secret=True,
               help='DEPRECATED - Database connection string.',
               ),
]

cfg.CONF.register_opts(OLD_STORAGE_OPTS)


STORAGE_OPTS = [
    cfg.IntOpt('time_to_live',
               default=-1,
               help="Number of seconds that samples are kept "
               "in the database for (<= 0 means forever)."),
    cfg.StrOpt('metering_connection',
               default=None,
               help='The connection string used to connect to the meteting '
               'database. (if unset, connection is used)'),
    cfg.StrOpt('alarm_connection',
               default=None,
               help='The connection string used to connect to the alarm '
               'database. (if unset, connection is used)'),
]

cfg.CONF.register_opts(STORAGE_OPTS, group='database')

cfg.CONF.import_opt('connection',
                    'ceilometer.openstack.common.db.options',
                    group='database')


class StorageBadVersion(Exception):
    """Error raised when the storage backend version is not good enough."""


class StorageBadAggregate(Exception):
    """Error raised when an aggregate is unacceptable to storage backend."""
    code = 400


STORAGE_ALARM_METHOD = [
    'get_alarms', 'create_alarm', 'update_alarm', 'delete_alarm',
    'get_alarm_changes', 'record_alarm_change',
    'query_alarms', 'query_alarm_history',
]


class ConnectionProxy(object):
    """Proxy to the real connection object

    This proxy filter out method that must not be available for a driver
    namespace for driver not yet moved to the ceilometer/alarm/storage subtree.

    This permit to migrate each driver in a different patch.

    This class will be removed when all drivers have been splitted and moved to
    the new subtree.
    """

    def __init__(self, conn, namespace):
        self._conn = conn
        self._namespace = namespace

        # NOTE(sileht): private object used in pymongo storage tests
        if hasattr(self._conn, 'db'):
            self.db = self._conn.db

    def get_meter_statistics(self, *args, **kwargs):
        # NOTE(sileht): must be defined to have mock working in
        # test_compute_duration_by_resource_scenarios
        method = self.__getattr__('get_meter_statistics')
        return method(*args, **kwargs)

    def __getattr__(self, attr):
        # NOTE(sileht): this can raise the real AttributeError
        value = getattr(self._conn, attr)
        is_shared = attr in ['upgrade', 'clear', 'get_capabilities',
                             'get_storage_capabilities']
        is_alarm = (self._namespace == 'ceilometer.alarm.storage'
                    and attr in STORAGE_ALARM_METHOD)
        is_metering = (self._namespace == 'ceilometer.metering.storage'
                       and attr not in STORAGE_ALARM_METHOD)
        if is_shared or is_alarm or is_metering:
            return value
        # NOTE(sileht): we try to access to an attribute not allowed for
        # this namespace
        raise AttributeError(
            'forbidden access to the hidden attribute %s for %s',
            attr, self._namespace)


def get_connection_from_config(conf, purpose=None):
    if conf.database_connection:
        conf.set_override('connection', conf.database_connection,
                          group='database')
    namespace = 'ceilometer.metering.storage'
    url = conf.database.connection
    if purpose:
        namespace = 'ceilometer.%s.storage' % purpose
        url = getattr(conf.database, '%s_connection' % purpose) or url
    return get_connection(url, namespace)


def get_connection(url, namespace):
    """Return an open connection to the database."""
    engine_name = urlparse.urlparse(url).scheme
    LOG.debug(_('looking for %(name)r driver in %(namespace)r') % (
              {'name': engine_name, 'namespace': namespace}))
    mgr = driver.DriverManager(namespace, engine_name)
    return ConnectionProxy(mgr.driver(url), namespace)


class SampleFilter(object):
    """Holds the properties for building a query from a meter/sample filter.

    :param user: The sample owner.
    :param project: The sample project.
    :param start: Earliest time point in the request.
    :param start_timestamp_op: Earliest timestamp operation in the request.
    :param end: Latest time point in the request.
    :param end_timestamp_op: Latest timestamp operation in the request.
    :param resource: Optional filter for resource id.
    :param meter: Optional filter for meter type using the meter name.
    :param source: Optional source filter.
    :param message_id: Optional sample_id filter.
    :param metaquery: Optional filter on the metadata
    """
    def __init__(self, user=None, project=None,
                 start=None, start_timestamp_op=None,
                 end=None, end_timestamp_op=None,
                 resource=None, meter=None,
                 source=None, message_id=None,
                 metaquery=None):
        self.user = user
        self.project = project
        self.start = utils.sanitize_timestamp(start)
        self.start_timestamp_op = start_timestamp_op
        self.end = utils.sanitize_timestamp(end)
        self.end_timestamp_op = end_timestamp_op
        self.resource = resource
        self.meter = meter
        self.source = source
        self.metaquery = metaquery or {}
        self.message_id = message_id


class EventFilter(object):
    """Properties for building an Event query.

    :param start_time: UTC start datetime (mandatory)
    :param end_time: UTC end datetime (mandatory)
    :param event_type: the name of the event. None for all.
    :param message_id: the message_id of the event. None for all.
    :param traits_filter: the trait filter dicts, all of which are optional.
      This parameter is a list of dictionaries that specify trait values:

    .. code-block:: python

        {'key': <key>,
        'string': <value>,
        'integer': <value>,
        'datetime': <value>,
        'float': <value>,
        'op': <eq, lt, le, ne, gt or ge> }
    """

    def __init__(self, start_time=None, end_time=None, event_type=None,
                 message_id=None, traits_filter=None):
        self.start_time = utils.sanitize_timestamp(start_time)
        self.end_time = utils.sanitize_timestamp(end_time)
        self.message_id = message_id
        self.event_type = event_type
        self.traits_filter = traits_filter or []

    def __repr__(self):
        return ("<EventFilter(start_time: %s,"
                " end_time: %s,"
                " event_type: %s,"
                " traits: %s)>" %
                (self.start_time,
                 self.end_time,
                 self.event_type,
                 six.text_type(self.traits_filter)))
