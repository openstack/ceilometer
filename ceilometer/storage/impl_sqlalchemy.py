# -*- encoding: utf-8 -*-
#
# Author: John Tran <jhtran@att.com>
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
"""SQLAlchemy storage backend
"""

import copy
import datetime

from ceilometer.openstack.common import log
from ceilometer.storage import base
from ceilometer.storage.sqlalchemy.models import Meter, Project, Resource
from ceilometer.storage.sqlalchemy.models import Source, User
from ceilometer.storage.sqlalchemy.session import func
import ceilometer.storage.sqlalchemy.session as sqlalchemy_session

LOG = log.getLogger(__name__)


class SQLAlchemyStorage(base.StorageEngine):
    """Put the data into a SQLAlchemy database

    Tables:

    - user
      - { id: user uuid }
    - source
      - { id: source id }
    - project
      - { id: project uuid }
    - meter
      - the raw incoming data
      - { id: meter id
          counter_name: counter name
          user_id: user uuid            (->user.id)
          project_id: project uuid      (->project.id)
          resource_id: resource uuid    (->resource.id)
          resource_metadata: metadata dictionaries
          counter_type: counter type
          counter_volume: counter volume
          timestamp: datetime
          message_signature: message signature
          message_id: message uuid
          }
    - resource
      - the metadata for resources
      - { id: resource uuid
          resource_metadata: metadata dictionaries
          received_timestamp: received datetime
          timestamp: datetime
          project_id: project uuid      (->project.id)
          user_id: user uuid            (->user.id)
          }
    - sourceassoc
      - the relationships
      - { meter_id: meter id            (->meter.id)
          project_id: project uuid      (->project.id)
          resource_id: resource uuid    (->resource.id)
          user_id: user uuid            (->user.id)
          source_id: source id          (->source.id)
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
        return Connection(conf)


def make_query_from_filter(query, event_filter, require_meter=True):
    """Return a query dictionary based on the settings in the filter.

    :param filter: EventFilter instance
    :param require_meter: If true and the filter does not have a meter,
                          raise an error.
    """

    if event_filter.meter:
        query = query.filter(Meter.counter_name == event_filter.meter)
    elif require_meter:
        raise RuntimeError('Missing required meter specifier')
    if event_filter.source:
        query = query.filter_by(source=event_filter.source)
    if event_filter.start:
        ts_start = event_filter.start
        query = query.filter(Meter.timestamp >= ts_start)
    if event_filter.end:
        ts_end = event_filter.end
        query = query.filter(Meter.timestamp < ts_end)
    if event_filter.user:
        query = query.filter_by(user_id=event_filter.user)
    elif event_filter.project:
        query = query.filter_by(project_id=event_filter.project)
    if event_filter.resource:
        query = query.filter_by(resource_id=event_filter.resource)

    return query


class Connection(base.Connection):
    """SqlAlchemy connection.
    """

    def __init__(self, conf):
        LOG.info('connecting to %s', conf.database_connection)
        self.session = self._get_connection(conf)
        return

    def _get_connection(self, conf):
        """Return a connection to the database.
        """
        return sqlalchemy_session.get_session()

    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter
        """
        if data['source']:
            source = self.session.query(Source).get(data['source'])
            if not source:
                source = Source(id=data['source'])
                self.session.add(source)
        else:
            source = None

        # create/update user && project, add/update their sources list
        if data['user_id']:
            user = self.session.merge(User(id=str(data['user_id'])))
            if not filter(lambda x: x.id == source.id, user.sources):
                user.sources.append(source)
        else:
            user = None

        if data['project_id']:
            project = self.session.merge(Project(id=str(data['project_id'])))
            if not filter(lambda x: x.id == source.id, project.sources):
                project.sources.append(source)
        else:
            project = None

        # Record the updated resource metadata
        rtimestamp = datetime.datetime.utcnow()
        rmetadata = data['resource_metadata']

        resource = self.session.merge(Resource(id=str(data['resource_id'])))
        if not filter(lambda x: x.id == source.id, resource.sources):
            resource.sources.append(source)
        resource.project = project
        resource.user = user
        resource.timestamp = data['timestamp']
        resource.received_timestamp = rtimestamp
        # Current metadata being used and when it was last updated.
        resource.resource_metadata = rmetadata
        # autoflush didn't catch this one, requires manual flush
        self.session.flush()

        # Record the raw data for the event.
        meter = Meter(counter_type=data['counter_type'],
                      counter_name=data['counter_name'], resource=resource)
        self.session.add(meter)
        if not filter(lambda x: x.id == source.id, meter.sources):
            meter.sources.append(source)
        meter.project = project
        meter.user = user
        meter.timestamp = data['timestamp']
        meter.resource_metadata = rmetadata
        meter.counter_volume = data['counter_volume']
        meter.message_signature = data['message_signature']
        meter.message_id = data['message_id']

        return

    def get_users(self, source=None):
        """Return an iterable of user id strings.

        :param source: Optional source filter.
        """
        query = model_query(User.id, session=self.session)
        if source is not None:
            query = query.filter(User.sources.any(id=source))
        return (x[0] for x in query.all())

    def get_projects(self, source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """
        query = model_query(Project.id, session=self.session)
        if source:
            query = query.filter(Project.sources.any(id=source))
        return (x[0] for x in query.all())

    def get_resources(self, user=None, project=None, source=None,
                      start_timestamp=None, end_timestamp=None):
        """Return an iterable of dictionaries containing resource information.

        { 'resource_id': UUID of the resource,
          'project_id': UUID of project owning the resource,
          'user_id': UUID of user owning the resource,
          'timestamp': UTC datetime of last update to the resource,
          'metadata': most current metadata for the resource,
          'meter': list of the meters reporting data for the resource,
          }

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param source: Optional source filter.
        :param start_timestamp: Optional modified timestamp start range.
        :param end_timestamp: Optional modified timestamp end range.
        """
        query = model_query(Resource, session=self.session)
        if user is not None:
            query = query.filter(Resource.user_id == user)
        if source is not None:
            query = query.filter(Resource.sources.any(id=source))
        if start_timestamp is not None:
            query = query.filter(Resource.timestamp >= start_timestamp)
        if end_timestamp:
            query = query.filter(Resource.timestamp < end_timestamp)
        if project is not None:
            query = query.filter(Resource.project_id == project)
        query = query.options(
                    sqlalchemy_session.sqlalchemy.orm.joinedload('meters'))

        for resource in query.all():
            r = row2dict(resource)
            # Replace the '_id' key with 'resource_id' to meet the
            # caller's expectations.
            r['resource_id'] = r['id']
            del r['id']
            # Replace the 'resource_metadata' with 'metadata'
            r['metadata'] = r['resource_metadata']
            del r['resource_metadata']
            # Replace the 'meters' with 'meter'
            r['meter'] = r['meters']
            del r['meters']
            yield r

    def get_meters(self, user=None, project=None, source=None,
                   resource=None):
        """Return an iterable of dictionaries containing meter information.

        { 'name': name of the meter,
          'type': type of the meter (guage, counter),
          'resource_id': UUID of the resource,
          'project_id': UUID of project owning the resource,
          'user_id': UUID of user owning the resource,
          }

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional ID of the resource.
        :param source: Optional source filter.
        """
        query = model_query(Resource, session=self.session)
        if user is not None:
            query = query.filter(Resource.user_id == user)
        if source is not None:
            query = query.filter(Resource.sources.any(id=source))
        if resource:
            query = query.filter(Resource.id == resource)
        if project is not None:
            query = query.filter(Resource.project_id == project)
        query = query.options(
                    sqlalchemy_session.sqlalchemy.orm.joinedload('meters'))

        for resource in query.all():
            meter_names = set()
            for meter in resource.meters:
                if meter.counter_name in meter_names:
                    continue
                meter_names.add(meter.counter_name)
                m = {}
                m['resource_id'] = resource.id
                m['project_id'] = resource.project_id
                m['user_id'] = resource.user_id
                m['name'] = meter.counter_name
                m['type'] = meter.counter_type
                yield m

    def get_raw_events(self, event_filter):
        """Return an iterable of raw event data as created by
        :func:`ceilometer.meter.meter_message_from_counter`.
        """
        query = model_query(Meter, session=self.session)
        query = make_query_from_filter(query, event_filter,
                                       require_meter=False)
        events = query.all()

        for e in events:
            # Remove the id generated by the database when
            # the event was inserted. It is an implementation
            # detail that should not leak outside of the driver.
            e = row2dict(e)
            del e['id']
            yield e

    def _make_volume_query(self, event_filter, counter_volume_func):
        """Returns complex Meter counter_volume query for max and sum"""
        subq = model_query(Meter.id, session=self.session)
        subq = make_query_from_filter(subq, event_filter, require_meter=False)
        subq = subq.subquery()
        mainq = self.session.query(Resource.id, counter_volume_func)
        mainq = mainq.join(Meter).group_by(Resource.id)
        return mainq.filter(Meter.id.in_(subq))

    def get_volume_sum(self, event_filter):
        counter_volume_func = func.sum(Meter.counter_volume)
        query = self._make_volume_query(event_filter, counter_volume_func)
        results = query.all()
        return ({'resource_id': x, 'value': y} for x, y in results)

    def get_volume_max(self, event_filter):
        counter_volume_func = func.max(Meter.counter_volume)
        query = self._make_volume_query(event_filter, counter_volume_func)
        results = query.all()
        return ({'resource_id': x, 'value': y} for x, y in results)

    def get_event_interval(self, event_filter):
        """Return the min and max timestamps from events,
        using the event_filter to limit the events seen.

        ( datetime.datetime(), datetime.datetime() )
        """
        query = self.session.query(func.min(Meter.timestamp),
                                   func.max(Meter.timestamp))
        query = make_query_from_filter(query, event_filter)
        results = query.all()
        a_min, a_max = results[0]
        return (a_min, a_max)


############################


def model_query(*args, **kwargs):
    """Query helper

    :param session: if present, the session to use
    """
    session = kwargs.get('session') or sqlalchemy_session.get_session()
    query = session.query(*args)
    return query


def row2dict(row, srcflag=None):
    """Convert User, Project, Meter, Resource instance to dictionary object
       with nested Source(s) and Meter(s)
    """
    d = copy.copy(row.__dict__)
    for col in ['_sa_instance_state', 'sources']:
        if col in d:
            del d[col]
    if not srcflag:
        d['sources'] = map(lambda x: row2dict(x, True), row.sources)
        if d.get('meters') is not None:
            d['meters'] = map(lambda x: row2dict(x, True), d['meters'])
    return d
