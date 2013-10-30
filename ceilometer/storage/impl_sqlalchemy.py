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
import datetime
import operator
import os
import types

from sqlalchemy import and_
from sqlalchemy import func
from sqlalchemy import desc
from sqlalchemy.orm import aliased

from ceilometer.openstack.common.db import exception as dbexc
import ceilometer.openstack.common.db.sqlalchemy.session as sqlalchemy_session
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer.storage import base
from ceilometer.storage import models as api_models
from ceilometer.storage.sqlalchemy import migration
from ceilometer.storage.sqlalchemy.models import Alarm
from ceilometer.storage.sqlalchemy.models import AlarmChange
from ceilometer.storage.sqlalchemy.models import Base
from ceilometer.storage.sqlalchemy.models import Event
from ceilometer.storage.sqlalchemy.models import Meter
from ceilometer.storage.sqlalchemy.models import MetaBool
from ceilometer.storage.sqlalchemy.models import MetaFloat
from ceilometer.storage.sqlalchemy.models import MetaInt
from ceilometer.storage.sqlalchemy.models import MetaText
from ceilometer.storage.sqlalchemy.models import Project
from ceilometer.storage.sqlalchemy.models import Resource
from ceilometer.storage.sqlalchemy.models import Source
from ceilometer.storage.sqlalchemy.models import Trait
from ceilometer.storage.sqlalchemy.models import UniqueName
from ceilometer.storage.sqlalchemy.models import User
from ceilometer import utils

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

    @staticmethod
    def get_connection(conf):
        """Return a Connection instance based on the configuration settings.
        """
        return Connection(conf)


META_TYPE_MAP = {bool: MetaBool,
                 str: MetaText,
                 unicode: MetaText,
                 types.NoneType: MetaText,
                 int: MetaInt,
                 long: MetaInt,
                 float: MetaFloat}


def apply_metaquery_filter(session, query, metaquery):
    """Apply provided metaquery filter to existing query.

    :param session: session used for original query
    :param query: Query instance
    :param metaquery: dict with metadata to match on.
    """

    for k, v in metaquery.iteritems():
        key = k[9:]  # strip out 'metadata.' prefix
        try:
            _model = META_TYPE_MAP[type(v)]
        except KeyError:
            raise NotImplementedError(_('Query on %(key)s is of %(value)s '
                                        'type and is not supported') %
                                      {"key": k, "value": type(v)})
        else:
            meta_q = session.query(_model).\
                filter(and_(_model.meta_key == key,
                            _model.value == v)).subquery()
            query = query.filter_by(id=meta_q.c.id)
    return query


def make_query_from_filter(session, query, sample_filter, require_meter=True):
    """Return a query dictionary based on the settings in the filter.

    :param filter: SampleFilter instance
    :param require_meter: If true and the filter does not have a meter,
                          raise an error.
    """

    if sample_filter.meter:
        query = query.filter(Meter.counter_name == sample_filter.meter)
    elif require_meter:
        raise RuntimeError(_('Missing required meter specifier'))
    if sample_filter.source:
        query = query.filter(Meter.sources.any(id=sample_filter.source))
    if sample_filter.start:
        ts_start = sample_filter.start
        if sample_filter.start_timestamp_op == 'gt':
            query = query.filter(Meter.timestamp > ts_start)
        else:
            query = query.filter(Meter.timestamp >= ts_start)
    if sample_filter.end:
        ts_end = sample_filter.end
        if sample_filter.end_timestamp_op == 'le':
            query = query.filter(Meter.timestamp <= ts_end)
        else:
            query = query.filter(Meter.timestamp < ts_end)
    if sample_filter.user:
        query = query.filter_by(user_id=sample_filter.user)
    if sample_filter.project:
        query = query.filter_by(project_id=sample_filter.project)
    if sample_filter.resource:
        query = query.filter_by(resource_id=sample_filter.resource)

    if sample_filter.metaquery:
        query = apply_metaquery_filter(session, query,
                                       sample_filter.metaquery)

    return query


class Connection(base.Connection):
    """SqlAlchemy connection."""

    def __init__(self, conf):
        url = conf.database.connection
        if url == 'sqlite://':
            conf.database.connection = \
                os.environ.get('CEILOMETER_TEST_SQL_URL', url)

    def upgrade(self):
        session = sqlalchemy_session.get_session()
        migration.db_sync(session.get_bind())

    def clear(self):
        session = sqlalchemy_session.get_session()
        engine = session.get_bind()
        for table in reversed(Base.metadata.sorted_tables):
            engine.execute(table.delete())

    @staticmethod
    def record_metering_data(data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter
        """
        session = sqlalchemy_session.get_session()
        with session.begin():
            if data['source']:
                source = session.query(Source).get(data['source'])
                if not source:
                    source = Source(id=data['source'])
                    session.add(source)
            else:
                source = None

            # create/update user && project, add/update their sources list
            if data['user_id']:
                user = session.merge(User(id=str(data['user_id'])))
                if not filter(lambda x: x.id == source.id, user.sources):
                    user.sources.append(source)
            else:
                user = None

            if data['project_id']:
                project = session.merge(Project(id=str(data['project_id'])))
                if not filter(lambda x: x.id == source.id, project.sources):
                    project.sources.append(source)
            else:
                project = None

            # Record the updated resource metadata
            rmetadata = data['resource_metadata']

            resource = session.merge(Resource(id=str(data['resource_id'])))
            if not filter(lambda x: x.id == source.id, resource.sources):
                resource.sources.append(source)
            resource.project = project
            resource.user = user
            # Current metadata being used and when it was last updated.
            resource.resource_metadata = rmetadata

            # Record the raw data for the meter.
            meter = Meter(counter_type=data['counter_type'],
                          counter_unit=data['counter_unit'],
                          counter_name=data['counter_name'], resource=resource)
            session.add(meter)
            if not filter(lambda x: x.id == source.id, meter.sources):
                meter.sources.append(source)
            meter.project = project
            meter.user = user
            meter.timestamp = data['timestamp']
            meter.resource_metadata = rmetadata
            meter.counter_volume = data['counter_volume']
            meter.message_signature = data['message_signature']
            meter.message_id = data['message_id']
            session.flush()

            if rmetadata:
                if isinstance(rmetadata, dict):
                    for key, v in utils.dict_to_keyval(rmetadata):
                        try:
                            _model = META_TYPE_MAP[type(v)]
                        except KeyError:
                            LOG.warn(_("Unknown metadata type. Key (%s) will "
                                       "not be queryable."), key)
                        else:
                            session.add(_model(id=meter.id,
                                               meta_key=key,
                                               value=v))

            session.flush()

    @staticmethod
    def clear_expired_metering_data(ttl):
        """Clear expired data from the backend storage system according to the
        time-to-live.

        :param ttl: Number of seconds to keep records for.

        """
        session = sqlalchemy_session.get_session()
        query = session.query(Meter.id)
        end = timeutils.utcnow() - datetime.timedelta(seconds=ttl)
        query = query.filter(Meter.timestamp < end)
        query.delete()

        query = session.query(User.id).filter(~User.id.in_(
            session.query(Meter.user_id).group_by(Meter.user_id)
        ))
        query.delete(synchronize_session='fetch')

        query = session.query(Project.id).filter(~Project.id.in_(
            session.query(Meter.project_id).group_by(Meter.project_id)
        ))
        query.delete(synchronize_session='fetch')

        query = session.query(Resource.id).filter(~Resource.id.in_(
            session.query(Meter.resource_id).group_by(Meter.resource_id)
        ))
        query.delete(synchronize_session='fetch')

    @staticmethod
    def get_users(source=None):
        """Return an iterable of user id strings.

        :param source: Optional source filter.
        """
        session = sqlalchemy_session.get_session()
        query = session.query(User.id)
        if source is not None:
            query = query.filter(User.sources.any(id=source))
        return (x[0] for x in query.all())

    @staticmethod
    def get_projects(source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """
        session = sqlalchemy_session.get_session()
        query = session.query(Project.id)
        if source:
            query = query.filter(Project.sources.any(id=source))
        return (x[0] for x in query.all())

    @staticmethod
    def get_resources(user=None, project=None, source=None,
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None,
                      metaquery={}, resource=None, pagination=None):
        """Return an iterable of api_models.Resource instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param source: Optional source filter.
        :param start_timestamp: Optional modified timestamp start range.
        :param start_timestamp_op: Optonal start time operator, like gt, ge.
        :param end_timestamp: Optional modified timestamp end range.
        :param end_timestamp_op: Optional end time operator, like lt, le.
        :param metaquery: Optional dict with metadata to match on.
        :param resource: Optional resource filter.
        :param pagination: Optional pagination query.
        """

        # We probably want to raise these early, since we don't know from here
        # if they will be handled. We don't want extra wait or work for it to
        # just fail.
        if pagination:
            raise NotImplementedError(_('Pagination not implemented'))

        # (thomasm) We need to get the max timestamp first, since that's the
        # most accurate. We also need to filter down in the subquery to
        # constrain what we have to JOIN on later.
        session = sqlalchemy_session.get_session()

        ts_subquery = session.query(
            Meter.resource_id,
            func.max(Meter.timestamp).label("max_ts"),
            func.min(Meter.timestamp).label("min_ts")
        ).group_by(Meter.resource_id)

        # Here are the basic 'eq' operation filters for the sample data.
        for column, value in [(Meter.resource_id, resource),
                              (Meter.user_id, user),
                              (Meter.project_id, project)]:
            if value:
                ts_subquery = ts_subquery.filter(column == value)

        if source:
            ts_subquery = ts_subquery.filter(
                Meter.sources.any(id=source))

        if metaquery:
            ts_subquery = apply_metaquery_filter(session,
                                                 ts_subquery,
                                                 metaquery)

        # Here we limit the samples being used to a specific time period,
        # if requested.
        if start_timestamp:
            if start_timestamp_op == 'gt':
                ts_subquery = ts_subquery.filter(
                    Meter.timestamp > start_timestamp
                )
            else:
                ts_subquery = ts_subquery.filter(
                    Meter.timestamp >= start_timestamp
                )
        if end_timestamp:
            if end_timestamp_op == 'le':
                ts_subquery = ts_subquery.filter(
                    Meter.timestamp <= end_timestamp
                )
            else:
                ts_subquery = ts_subquery.filter(
                    Meter.timestamp < end_timestamp
                )
        ts_subquery = ts_subquery.subquery()

        # Now we need to get the max Meter.id out of the leftover results, to
        # break any ties.
        agg_subquery = session.query(
            func.max(Meter.id).label("max_id"),
            ts_subquery
        ).filter(
            Meter.resource_id == ts_subquery.c.resource_id,
            Meter.timestamp == ts_subquery.c.max_ts
        ).group_by(
            ts_subquery.c.resource_id,
            ts_subquery.c.max_ts,
            ts_subquery.c.min_ts
        ).subquery()

        query = session.query(
            Meter,
            agg_subquery.c.min_ts,
            agg_subquery.c.max_ts
        ).filter(
            Meter.id == agg_subquery.c.max_id
        )

        for meter, first_ts, last_ts in query.all():
            yield api_models.Resource(
                resource_id=meter.resource_id,
                project_id=meter.project_id,
                first_sample_timestamp=first_ts,
                last_sample_timestamp=last_ts,
                source=meter.sources[0].id,
                user_id=meter.user_id,
                metadata=meter.resource_metadata,
                meter=[
                    api_models.ResourceMeter(
                        counter_name=m.counter_name,
                        counter_type=m.counter_type,
                        counter_unit=m.counter_unit,
                    )
                    for m in meter.resource.meters
                ],
            )

    @staticmethod
    def get_meters(user=None, project=None, resource=None, source=None,
                   metaquery={}, pagination=None):
        """Return an iterable of api_models.Meter instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional ID of the resource.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param pagination: Optional pagination query.
        """

        if pagination:
            raise NotImplementedError(_('Pagination not implemented'))

        session = sqlalchemy_session.get_session()

        # Meter table will store large records and join with resource
        # will be very slow.
        # subquery_meter is used to reduce meter records
        # by selecting a record for each (resource_id, counter_name).
        # max() is used to choice a meter record, so the latest record
        # is selected for each (resource_id, counter_name).
        #
        subquery_meter = session.query(func.max(Meter.id).label('id')).\
            group_by(Meter.resource_id, Meter.counter_name).subquery()

        # The SQL of query_meter is essentially:
        #
        # SELECT meter.* FROM meter INNER JOIN
        #  (SELECT max(meter.id) AS id FROM meter
        #   GROUP BY meter.resource_id, meter.counter_name) AS anon_2
        # ON meter.id = anon_2.id
        #
        query_meter = session.query(Meter).\
            join(subquery_meter, Meter.id == subquery_meter.c.id)

        if metaquery:
            query_meter = apply_metaquery_filter(session,
                                                 query_meter,
                                                 metaquery)

        alias_meter = aliased(Meter, query_meter.subquery())
        query = session.query(Resource, alias_meter).join(
            alias_meter, Resource.id == alias_meter.resource_id)

        if user is not None:
            query = query.filter(Resource.user_id == user)
        if source is not None:
            query = query.filter(Resource.sources.any(id=source))
        if resource:
            query = query.filter(Resource.id == resource)
        if project is not None:
            query = query.filter(Resource.project_id == project)

        for resource, meter in query.all():
            yield api_models.Meter(
                name=meter.counter_name,
                type=meter.counter_type,
                unit=meter.counter_unit,
                resource_id=resource.id,
                project_id=resource.project_id,
                source=resource.sources[0].id,
                user_id=resource.user_id)

    @staticmethod
    def get_samples(sample_filter, limit=None):
        """Return an iterable of api_models.Samples.

        :param sample_filter: Filter.
        :param limit: Maximum number of results to return.
        """
        if limit == 0:
            return

        session = sqlalchemy_session.get_session()
        query = session.query(Meter)
        query = make_query_from_filter(session, query, sample_filter,
                                       require_meter=False)
        if limit:
            query = query.limit(limit)
        samples = query.from_self().order_by(desc(Meter.timestamp)).all()

        for s in samples:
            # Remove the id generated by the database when
            # the sample was inserted. It is an implementation
            # detail that should not leak outside of the driver.
            yield api_models.Sample(
                # Replace 'sources' with 'source' to meet the caller's
                # expectation, Meter.sources contains one and only one
                # source in the current implementation.
                source=s.sources[0].id,
                counter_name=s.counter_name,
                counter_type=s.counter_type,
                counter_unit=s.counter_unit,
                counter_volume=s.counter_volume,
                user_id=s.user_id,
                project_id=s.project_id,
                resource_id=s.resource_id,
                timestamp=s.timestamp,
                resource_metadata=s.resource_metadata,
                message_id=s.message_id,
                message_signature=s.message_signature,
            )

    @staticmethod
    def _make_stats_query(sample_filter, groupby):
        select = [
            Meter.counter_unit.label('unit'),
            func.min(Meter.timestamp).label('tsmin'),
            func.max(Meter.timestamp).label('tsmax'),
            func.avg(Meter.counter_volume).label('avg'),
            func.sum(Meter.counter_volume).label('sum'),
            func.min(Meter.counter_volume).label('min'),
            func.max(Meter.counter_volume).label('max'),
            func.count(Meter.counter_volume).label('count'),
        ]

        session = sqlalchemy_session.get_session()

        if groupby:
            group_attributes = [getattr(Meter, g) for g in groupby]
            select.extend(group_attributes)

        query = session.query(*select)

        if groupby:
            query = query.group_by(*group_attributes)

        return make_query_from_filter(session, query, sample_filter)

    @staticmethod
    def _stats_result_to_model(result, period, period_start,
                               period_end, groupby):
        duration = (timeutils.delta_seconds(result.tsmin, result.tsmax)
                    if result.tsmin is not None and result.tsmax is not None
                    else None)
        return api_models.Statistics(
            unit=result.unit,
            count=int(result.count),
            min=result.min,
            max=result.max,
            avg=result.avg,
            sum=result.sum,
            duration_start=result.tsmin,
            duration_end=result.tsmax,
            duration=duration,
            period=period,
            period_start=period_start,
            period_end=period_end,
            groupby=(dict((g, getattr(result, g)) for g in groupby)
                     if groupby else None)
        )

    def get_meter_statistics(self, sample_filter, period=None, groupby=None):
        """Return an iterable of api_models.Statistics instances containing
        meter statistics described by the query parameters.

        The filter must have a meter value set.

        """
        if groupby:
            for group in groupby:
                if group not in ['user_id', 'project_id', 'resource_id']:
                    raise NotImplementedError(
                        _("Unable to group by these fields"))

        if not period:
            for res in self._make_stats_query(sample_filter, groupby):
                if res.count:
                    yield self._stats_result_to_model(res, 0,
                                                      res.tsmin, res.tsmax,
                                                      groupby)
            return

        if not sample_filter.start or not sample_filter.end:
            res = self._make_stats_query(sample_filter, None).first()

        query = self._make_stats_query(sample_filter, groupby)
        # HACK(jd) This is an awful method to compute stats by period, but
        # since we're trying to be SQL agnostic we have to write portable
        # code, so here it is, admire! We're going to do one request to get
        # stats by period. We would like to use GROUP BY, but there's no
        # portable way to manipulate timestamp in SQL, so we can't.
        for period_start, period_end in base.iter_period(
                sample_filter.start or res.tsmin,
                sample_filter.end or res.tsmax,
                period):
            q = query.filter(Meter.timestamp >= period_start)
            q = q.filter(Meter.timestamp < period_end)
            for r in q.all():
                if r.count:
                    yield self._stats_result_to_model(
                        result=r,
                        period=int(timeutils.delta_seconds(period_start,
                                                           period_end)),
                        period_start=period_start,
                        period_end=period_end,
                        groupby=groupby
                    )

    @staticmethod
    def _row_to_alarm_model(row):
        return api_models.Alarm(alarm_id=row.id,
                                enabled=row.enabled,
                                type=row.type,
                                name=row.name,
                                description=row.description,
                                timestamp=row.timestamp,
                                user_id=row.user_id,
                                project_id=row.project_id,
                                state=row.state,
                                state_timestamp=row.state_timestamp,
                                ok_actions=row.ok_actions,
                                alarm_actions=row.alarm_actions,
                                insufficient_data_actions=
                                row.insufficient_data_actions,
                                rule=row.rule,
                                repeat_actions=row.repeat_actions)

    def get_alarms(self, name=None, user=None,
                   project=None, enabled=None, alarm_id=None, pagination=None):
        """Yields a lists of alarms that match filters
        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param enabled: Optional boolean to list disable alarm.
        :param alarm_id: Optional alarm_id to return one alarm.
        :param pagination: Optional pagination query.
        """

        if pagination:
            raise NotImplementedError(_('Pagination not implemented'))

        session = sqlalchemy_session.get_session()
        query = session.query(Alarm)
        if name is not None:
            query = query.filter(Alarm.name == name)
        if enabled is not None:
            query = query.filter(Alarm.enabled == enabled)
        if user is not None:
            query = query.filter(Alarm.user_id == user)
        if project is not None:
            query = query.filter(Alarm.project_id == project)
        if alarm_id is not None:
            query = query.filter(Alarm.id == alarm_id)

        return (self._row_to_alarm_model(x) for x in query.all())

    def create_alarm(self, alarm):
        """Create an alarm.

        :param alarm: The alarm to create.
        """
        session = sqlalchemy_session.get_session()
        with session.begin():
            session.merge(User(id=alarm.user_id))
            session.merge(Project(id=alarm.project_id))
            alarm_row = Alarm(id=alarm.alarm_id)
            alarm_row.update(alarm.as_dict())
            session.add(alarm_row)
            session.flush()

        return self._row_to_alarm_model(alarm_row)

    def update_alarm(self, alarm):
        """Update an alarm.

        :param alarm: the new Alarm to update
        """
        session = sqlalchemy_session.get_session()
        with session.begin():
            alarm_row = session.merge(Alarm(id=alarm.alarm_id))
            alarm_row.update(alarm.as_dict())
            session.flush()

        return self._row_to_alarm_model(alarm_row)

    @staticmethod
    def delete_alarm(alarm_id):
        """Delete a alarm

        :param alarm_id: ID of the alarm to delete
        """
        session = sqlalchemy_session.get_session()
        with session.begin():
            session.query(Alarm).filter(Alarm.id == alarm_id).delete()
            session.flush()

    @staticmethod
    def _row_to_alarm_change_model(row):
        return api_models.AlarmChange(event_id=row.event_id,
                                      alarm_id=row.alarm_id,
                                      type=row.type,
                                      detail=row.detail,
                                      user_id=row.user_id,
                                      project_id=row.project_id,
                                      on_behalf_of=row.on_behalf_of,
                                      timestamp=row.timestamp)

    def get_alarm_changes(self, alarm_id, on_behalf_of,
                          user=None, project=None, type=None,
                          start_timestamp=None, start_timestamp_op=None,
                          end_timestamp=None, end_timestamp_op=None):
        """Yields list of AlarmChanges describing alarm history

        Changes are always sorted in reverse order of occurence, given
        the importance of currency.

        Segregation for non-administrative users is done on the basis
        of the on_behalf_of parameter. This allows such users to have
        visibility on both the changes initiated by themselves directly
        (generally creation, rule changes, or deletion) and also on those
        changes initiated on their behalf by the alarming service (state
        transitions after alarm thresholds are crossed).

        :param alarm_id: ID of alarm to return changes for
        :param on_behalf_of: ID of tenant to scope changes query (None for
                             administrative user, indicating all projects)
        :param user: Optional ID of user to return changes for
        :param project: Optional ID of project to return changes for
        :project type: Optional change type
        :param start_timestamp: Optional modified timestamp start range
        :param start_timestamp_op: Optional timestamp start range operation
        :param end_timestamp: Optional modified timestamp end range
        :param end_timestamp_op: Optional timestamp end range operation
        """
        session = sqlalchemy_session.get_session()
        query = session.query(AlarmChange)
        query = query.filter(AlarmChange.alarm_id == alarm_id)

        if on_behalf_of is not None:
            query = query.filter(AlarmChange.on_behalf_of == on_behalf_of)
        if user is not None:
            query = query.filter(AlarmChange.user_id == user)
        if project is not None:
            query = query.filter(AlarmChange.project_id == project)
        if type is not None:
            query = query.filter(AlarmChange.type == type)
        if start_timestamp:
            if start_timestamp_op == 'gt':
                query = query.filter(AlarmChange.timestamp > start_timestamp)
            else:
                query = query.filter(AlarmChange.timestamp >= start_timestamp)
        if end_timestamp:
            if end_timestamp_op == 'le':
                query = query.filter(AlarmChange.timestamp <= end_timestamp)
            else:
                query = query.filter(AlarmChange.timestamp < end_timestamp)

        query = query.order_by(desc(AlarmChange.timestamp))
        return (self._row_to_alarm_change_model(x) for x in query.all())

    def record_alarm_change(self, alarm_change):
        """Record alarm change event.
        """
        session = sqlalchemy_session.get_session()
        with session.begin():
            session.merge(User(id=alarm_change['user_id']))
            session.merge(Project(id=alarm_change['project_id']))
            session.merge(Project(id=alarm_change['on_behalf_of']))
            alarm_change_row = AlarmChange(event_id=alarm_change['event_id'])
            alarm_change_row.update(alarm_change)
            session.add(alarm_change_row)
            session.flush()

    @staticmethod
    def _get_unique(session, key):
        return session.query(UniqueName).filter(UniqueName.key == key).first()

    def _get_or_create_unique_name(self, key, session=None):
        """Find the UniqueName entry for a given key, creating
           one if necessary.

           This may result in a flush.
        """
        if session is None:
            session = sqlalchemy_session.get_session()
        with session.begin(subtransactions=True):
            unique = self._get_unique(session, key)
            if not unique:
                unique = UniqueName(key=key)
                session.add(unique)
                session.flush()
        return unique

    def _make_trait(self, trait_model, event, session=None):
        """Make a new Trait from a Trait model.

        Doesn't flush or add to session.
        """
        name = self._get_or_create_unique_name(trait_model.name,
                                               session=session)
        value_map = Trait._value_map
        values = {'t_string': None, 't_float': None,
                  't_int': None, 't_datetime': None}
        value = trait_model.value
        if trait_model.dtype == api_models.Trait.DATETIME_TYPE:
            value = utils.dt_to_decimal(value)
        values[value_map[trait_model.dtype]] = value
        return Trait(name, event, trait_model.dtype, **values)

    def _record_event(self, session, event_model):
        """Store a single Event, including related Traits.
        """
        with session.begin(subtransactions=True):
            unique = self._get_or_create_unique_name(event_model.event_name,
                                                     session=session)

            generated = utils.dt_to_decimal(event_model.generated)
            event = Event(event_model.message_id, unique, generated)
            session.add(event)

            new_traits = []
            if event_model.traits:
                for trait in event_model.traits:
                    t = self._make_trait(trait, event, session=session)
                    session.add(t)
                    new_traits.append(t)

        # Note: we don't flush here, explicitly (unless a new uniquename
        # does it). Otherwise, just wait until all the Events are staged.
        return (event, new_traits)

    def record_events(self, event_models):
        """Write the events to SQL database via sqlalchemy.

        :param event_models: a list of model.Event objects.

        Returns a list of events that could not be saved in a
        (reason, event) tuple. Reasons are enumerated in
        storage.model.Event
        """
        session = sqlalchemy_session.get_session()
        events = []
        problem_events = []
        for event_model in event_models:
            event = None
            try:
                with session.begin():
                    event = self._record_event(session, event_model)
                    session.flush()
            except dbexc.DBDuplicateEntry:
                problem_events.append((api_models.Event.DUPLICATE,
                                       event_model))
            except Exception as e:
                LOG.exception('Failed to record event: %s', e)
                problem_events.append((api_models.Event.UNKNOWN_PROBLEM,
                                       event_model))
            events.append(event)
        return problem_events

    def get_events(self, event_filter):
        """Return an iterable of model.Event objects.

        :param event_filter: EventFilter instance
        """

        start = utils.dt_to_decimal(event_filter.start)
        end = utils.dt_to_decimal(event_filter.end)
        session = sqlalchemy_session.get_session()
        with session.begin():
            event_query_filters = [Event.generated >= start,
                                   Event.generated <= end]
            sub_query = session.query(Event.id)\
                .join(Trait, Trait.event_id == Event.id)

            if event_filter.event_name:
                event_name = self._get_unique(session, event_filter.event_name)
                event_query_filters.append(Event.unique_name == event_name)

            sub_query = sub_query.filter(*event_query_filters)

            event_models_dict = {}
            if event_filter.traits:
                for key, value in event_filter.traits.iteritems():
                    if key == 'key':
                        key = self._get_unique(session, value)
                        sub_query = sub_query.filter(Trait.name == key)
                    elif key == 't_string':
                        sub_query = sub_query.filter(Trait.t_string == value)
                    elif key == 't_int':
                        sub_query = sub_query.filter(Trait.t_int == value)
                    elif key == 't_datetime':
                        dt = utils.dt_to_decimal(value)
                        sub_query = sub_query.filter(Trait.t_datetime == dt)
                    elif key == 't_float':
                        sub_query = sub_query.filter(Trait.t_datetime == value)
            else:
                # Pre-populate event_models_dict to cover Events without traits
                events = session.query(Event).filter(*event_query_filters)
                for db_event in events.all():
                    generated = utils.decimal_to_dt(db_event.generated)
                    api_event = api_models.Event(db_event.message_id,
                                                 db_event.unique_name.key,
                                                 generated, [])
                    event_models_dict[db_event.id] = api_event

            sub_query = sub_query.subquery()

            all_data = session.query(Trait)\
                .join(sub_query, Trait.event_id == sub_query.c.id)

            # Now convert the sqlalchemy objects back into Models ...
            for trait in all_data.all():
                event = event_models_dict.get(trait.event_id)
                if not event:
                    generated = utils.decimal_to_dt(trait.event.generated)
                    event = api_models.Event(trait.event.message_id,
                                             trait.event.unique_name.key,
                                             generated, [])
                    event_models_dict[trait.event_id] = event
                value = trait.get_value()
                trait_model = api_models.Trait(trait.name.key, trait.t_type,
                                               value)
                event.append_trait(trait_model)

        event_models = event_models_dict.values()
        return sorted(event_models, key=operator.attrgetter('generated'))
