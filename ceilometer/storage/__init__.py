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
from oslo.db import options as db_options
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

db_options.set_defaults(cfg.CONF)
cfg.CONF.import_opt('connection', 'oslo.db.options', group='database')


class StorageBadVersion(Exception):
    """Error raised when the storage backend version is not good enough."""


class StorageBadAggregate(Exception):
    """Error raised when an aggregate is unacceptable to storage backend."""
    code = 400


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
    connection_scheme = urlparse.urlparse(url).scheme
    # SqlAlchemy connections specify may specify a 'dialect' or
    # 'dialect+driver'. Handle the case where driver is specified.
    engine_name = connection_scheme.split('+')[0]
    LOG.debug(_('looking for %(name)r driver in %(namespace)r') % (
              {'name': engine_name, 'namespace': namespace}))
    mgr = driver.DriverManager(namespace, engine_name)
    return mgr.driver(url)


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
