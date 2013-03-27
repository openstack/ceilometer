# -*- encoding: utf-8 -*-
#
# Author: John Tran <jhtran@att.com>
#         Julien Danjou <julien@danjou.info>
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

"""SQLAlchemy storage backend."""

from __future__ import absolute_import

import copy
import os
from sqlalchemy import func

from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer.storage import base
from ceilometer.storage.sqlalchemy import migration
from ceilometer.storage.sqlalchemy.models import Meter, Project, Resource
from ceilometer.storage.sqlalchemy.models import Source, User, Base
import ceilometer.storage.sqlalchemy.session as sqlalchemy_session

LOG = log.getLogger(__name__)


class SQLAlchemyStorage(base.StorageEngine):
    """Put the data into a SQLAlchemy database.

    Tables::

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
              counter_unit: counter unit
              counter_volume: counter volume
              timestamp: datetime
              message_signature: message signature
              message_id: message uuid
              }
        - resource
          - the metadata for resources
          - { id: resource uuid
              resource_metadata: metadata dictionaries
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
        """Register any configuration options used by this engine."""
        conf.register_opts(self.OPTIONS)

    @staticmethod
    def get_connection(conf):
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
        query = query.filter(Meter.sources.any(id=event_filter.source))
    if event_filter.start:
        ts_start = event_filter.start
        query = query.filter(Meter.timestamp >= ts_start)
    if event_filter.end:
        ts_end = event_filter.end
        query = query.filter(Meter.timestamp < ts_end)
    if event_filter.user:
        query = query.filter_by(user_id=event_filter.user)
    if event_filter.project:
        query = query.filter_by(project_id=event_filter.project)
    if event_filter.resource:
        query = query.filter_by(resource_id=event_filter.resource)

    if event_filter.metaquery:
        raise NotImplementedError('metaquery not implemented')

    return query


class Connection(base.Connection):
    """SqlAlchemy connection."""

    def __init__(self, conf):
        url = conf.database_connection
        if url == 'sqlite://':
            url = os.environ.get('CEILOMETER_TEST_SQL_URL', url)
        LOG.info('connecting to %s', url)
        self.session = sqlalchemy_session.get_session(url, conf)

    def upgrade(self, version=None):
        migration.db_sync(self.session.get_bind(), version=version)

    def clear(self):
        engine = self.session.get_bind()
        for table in reversed(Base.metadata.sorted_tables):
            engine.execute(table.delete())

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
        rmetadata = data['resource_metadata']

        resource = self.session.merge(Resource(id=str(data['resource_id'])))
        if not filter(lambda x: x.id == source.id, resource.sources):
            resource.sources.append(source)
        resource.project = project
        resource.user = user
        # Current metadata being used and when it was last updated.
        resource.resource_metadata = rmetadata
        # autoflush didn't catch this one, requires manual flush
        self.session.flush()

        # Record the raw data for the event.
        meter = Meter(counter_type=data['counter_type'],
                      counter_unit=data['counter_unit'],
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
        query = self.session.query(User.id)
        if source is not None:
            query = query.filter(User.sources.any(id=source))
        return (x[0] for x in query.all())

    def get_projects(self, source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """
        query = self.session.query(Project.id)
        if source:
            query = query.filter(Project.sources.any(id=source))
        return (x[0] for x in query.all())

    def get_resources(self, user=None, project=None, source=None,
                      start_timestamp=None, end_timestamp=None,
                      metaquery={}, resource=None):
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
        :param metaquery: Optional dict with metadata to match on.
        :param resource: Optional resource filter.
        """
        query = self.session.query(Meter,).group_by(Meter.resource_id)
        if user is not None:
            query = query.filter(Meter.user_id == user)
        if source is not None:
            query = query.filter(Meter.sources.any(id=source))
        if start_timestamp:
            query = query.filter(Meter.timestamp >= start_timestamp)
        if end_timestamp:
            query = query.filter(Meter.timestamp < end_timestamp)
        if project is not None:
            query = query.filter(Meter.project_id == project)
        if resource is not None:
            query = query.filter(Meter.resource_id == resource)
        if metaquery:
            raise NotImplementedError('metaquery not implemented')

        for meter in query.all():
            r = row2dict(meter.resource)
            r['resource_id'] = r['id']
            del r['id']
            # Replace the 'resource_metadata' with 'metadata'
            r['metadata'] = r['resource_metadata']
            del r['resource_metadata']
            r['meter'] = [
                {
                    'counter_name': meter.counter_name,
                    'counter_type': meter.counter_type,
                    'counter_unit': meter.counter_unit,
                }
                for meter in meter.resource.meters
            ]
            yield r

    def get_meters(self, user=None, project=None, resource=None, source=None,
                   metaquery={}):
        """Return an iterable of dictionaries containing meter information.

        { 'name': name of the meter,
          'type': type of the meter (guage, counter),
          'unit': unit of the meter,
          'resource_id': UUID of the resource,
          'project_id': UUID of project owning the resource,
          'user_id': UUID of user owning the resource,
          }

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional ID of the resource.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        """
        query = self.session.query(Resource)
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
        if metaquery:
            raise NotImplementedError('metaquery not implemented')

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
                m['unit'] = meter.counter_unit
                yield m

    def get_samples(self, event_filter):
        """Return an iterable of samples as created by
        :func:`ceilometer.meter.meter_message_from_counter`.
        """
        query = self.session.query(Meter)
        query = make_query_from_filter(query, event_filter,
                                       require_meter=False)
        samples = query.all()

        for s in samples:
            # Remove the id generated by the database when
            # the event was inserted. It is an implementation
            # detail that should not leak outside of the driver.
            s = row2dict(s)
            del s['id']
            # Replace 'sources' with 'source' to meet the caller's
            # expectation, Meter.sources contains one and only one
            # source in the current implementation.
            s['source'] = s['sources'][0]['id']
            del s['sources']
            yield s

    def _make_volume_query(self, event_filter, counter_volume_func):
        """Returns complex Meter counter_volume query for max and sum."""
        subq = self.session.query(Meter.id)
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
        """Return the min and max timestamps from samples,
        using the event_filter to limit the samples seen.

        ( datetime.datetime(), datetime.datetime() )
        """
        query = self.session.query(func.min(Meter.timestamp),
                                   func.max(Meter.timestamp))
        query = make_query_from_filter(query, event_filter)
        results = query.all()
        a_min, a_max = results[0]
        return (a_min, a_max)

    def _make_stats_query(self, event_filter):
        query = self.session.query(
            func.min(Meter.timestamp).label('tsmin'),
            func.max(Meter.timestamp).label('tsmax'),
            func.avg(Meter.counter_volume).label('avg'),
            func.sum(Meter.counter_volume).label('sum'),
            func.min(Meter.counter_volume).label('min'),
            func.max(Meter.counter_volume).label('max'),
            func.count(Meter.counter_volume).label('count'))

        return make_query_from_filter(query, event_filter)

    @staticmethod
    def _stats_result_to_dict(result, period, period_start, period_end):
        return {'count': int(result.count),
                'min': result.min,
                'max': result.max,
                'avg': result.avg,
                'sum': result.sum,
                'duration_start': result.tsmin,
                'duration_end': result.tsmax,
                'duration': timeutils.delta_seconds(result.tsmin,
                                                    result.tsmax),
                'period': period,
                'period_start': period_start,
                'period_end': period_end}

    def get_meter_statistics(self, event_filter, period=None):
        """Return a dictionary containing meter statistics.
        described by the query parameters.

        The filter must have a meter value set.

        { 'min':
          'max':
          'avg':
          'sum':
          'count':
          'period':
          'period_start':
          'period_end':
          'duration':
          'duration_start':
          'duration_end':
          }
        """

        if not period or not event_filter.start or not event_filter.end:
            res = self._make_stats_query(event_filter).all()[0]

        if not period:
            return [self._stats_result_to_dict(res, 0, res.tsmin, res.tsmax)]

        query = self._make_stats_query(event_filter)
        # HACK(jd) This is an awful method to compute stats by period, but
        # since we're trying to be SQL agnostic we have to write portable
        # code, so here it is, admire! We're going to do one request to get
        # stats by period. We would like to use GROUP BY, but there's no
        # portable way to manipulate timestamp in SQL, so we can't.
        results = []
        for period_start, period_end in base.iter_period(
                event_filter.start or res.tsmin,
                event_filter.end or res.tsmax,
                period):
            q = query.filter(Meter.timestamp >= period_start)
            q = q.filter(Meter.timestamp < period_end)
            r = q.all()[0]
            # Don't add results that didn't have any event
            if r.count:
                results.append(self._stats_result_to_dict(
                    result=r,
                    period=int(timeutils.delta_seconds(period_start,
                                                       period_end)),
                    period_start=period_start,
                    period_end=period_end,
                ))

        return results


def row2dict(row, srcflag=False):
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
