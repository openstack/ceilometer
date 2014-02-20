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
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy.orm import aliased

from ceilometer.openstack.common.db import exception as dbexc
import ceilometer.openstack.common.db.sqlalchemy.session as sqlalchemy_session
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer.storage import base
from ceilometer.storage import models as api_models
from ceilometer.storage.sqlalchemy import migration
from ceilometer.storage.sqlalchemy import models
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


META_TYPE_MAP = {bool: models.MetaBool,
                 str: models.MetaText,
                 unicode: models.MetaText,
                 types.NoneType: models.MetaText,
                 int: models.MetaBigInt,
                 long: models.MetaBigInt,
                 float: models.MetaFloat}


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

    :param session: session used for original query
    :param query: Query instance
    :param sample_filter: SampleFilter instance
    :param require_meter: If true and the filter does not have a meter,
                          raise an error.
    """

    if sample_filter.meter:
        query = query.filter(models.Meter.counter_name == sample_filter.meter)
    elif require_meter:
        raise RuntimeError(_('Missing required meter specifier'))
    if sample_filter.source:
        query = query.filter(models.Meter.sources.any(id=sample_filter.source))
    if sample_filter.start:
        ts_start = sample_filter.start
        if sample_filter.start_timestamp_op == 'gt':
            query = query.filter(models.Meter.timestamp > ts_start)
        else:
            query = query.filter(models.Meter.timestamp >= ts_start)
    if sample_filter.end:
        ts_end = sample_filter.end
        if sample_filter.end_timestamp_op == 'le':
            query = query.filter(models.Meter.timestamp <= ts_end)
        else:
            query = query.filter(models.Meter.timestamp < ts_end)
    if sample_filter.user:
        query = query.filter_by(user_id=sample_filter.user)
    if sample_filter.project:
        query = query.filter_by(project_id=sample_filter.project)
    if sample_filter.resource:
        query = query.filter_by(resource_id=sample_filter.resource)
    if sample_filter.message_id:
        query = query.filter_by(message_id=sample_filter.message_id)

    if sample_filter.metaquery:
        query = apply_metaquery_filter(session, query,
                                       sample_filter.metaquery)

    return query


class Connection(base.Connection):
    """SqlAlchemy connection."""

    operators = {"=": operator.eq,
                 "<": operator.lt,
                 ">": operator.gt,
                 "<=": operator.le,
                 "=<": operator.le,
                 ">=": operator.ge,
                 "=>": operator.ge,
                 "!=": operator.ne}
    complex_operators = {"or": or_,
                         "and": and_}
    ordering_functions = {"asc": asc,
                          "desc": desc}

    def __init__(self, conf):
        url = conf.database.connection
        if url == 'sqlite://':
            conf.database.connection = \
                os.environ.get('CEILOMETER_TEST_SQL_URL', url)

        # NOTE(Alexei_987) Related to bug #1271103
        #                  we steal objects from sqlalchemy_session
        #                  to manage their lifetime on our own.
        #                  This is needed to open several db connections
        self._engine = sqlalchemy_session.get_engine()
        self._maker = sqlalchemy_session.get_maker(self._engine)
        sqlalchemy_session._ENGINE = None
        sqlalchemy_session._MAKER = None

    def _get_db_session(self):
        return self._maker()

    def upgrade(self):
        migration.db_sync(self._engine)

    def clear(self):
        for table in reversed(models.Base.metadata.sorted_tables):
            self._engine.execute(table.delete())
        self._maker.close_all()
        self._engine.dispose()

    @staticmethod
    def _create_or_update(session, model_class, _id, source=None, **kwargs):
        if not _id:
            return None

        try:
            # create a nested session for the case of two call of
            # record_metering_data run in parallel to not fail the
            # record of this sample
            # (except for sqlite, that doesn't support nested
            # transaction and doesn't have concurrency problem)
            nested = session.connection().dialect.name != 'sqlite'

            # raise dbexc.DBDuplicateEntry manually for sqlite
            # to not break the current session
            if not nested and session.query(model_class).get(str(_id)):
                raise dbexc.DBDuplicateEntry()

            with session.begin(nested=nested,
                               subtransactions=not nested):
                obj = model_class(id=str(_id))
                session.add(obj)
        except dbexc.DBDuplicateEntry:
            # requery the object from the db if this is an other
            # parallel/previous call of record_metering_data that
            # have successfully created this object
            obj = session.query(model_class).get(str(_id))

        # update the object
        if source and not filter(lambda x: x.id == source.id, obj.sources):
            obj.sources.append(source)
        for k in kwargs:
            setattr(obj, k, kwargs[k])
        return obj

    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter
        """
        session = self._get_db_session()
        with session.begin():
            # Record the updated resource metadata
            rmetadata = data['resource_metadata']
            source = self._create_or_update(session, models.Source,
                                            data['source'])
            user = self._create_or_update(session, models.User,
                                          data['user_id'], source)
            project = self._create_or_update(session, models.Project,
                                             data['project_id'], source)
            resource = self._create_or_update(session, models.Resource,
                                              data['resource_id'], source,
                                              user=user, project=project,
                                              resource_metadata=rmetadata)

            # Record the raw data for the meter.
            meter = models.Meter(counter_type=data['counter_type'],
                                 counter_unit=data['counter_unit'],
                                 counter_name=data['counter_name'],
                                 resource=resource)
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

    def clear_expired_metering_data(self, ttl):
        """Clear expired data from the backend storage system according to the
        time-to-live.

        :param ttl: Number of seconds to keep records for.

        """

        session = self._get_db_session()
        with session.begin():
            end = timeutils.utcnow() - datetime.timedelta(seconds=ttl)
            meter_query = session.query(models.Meter)\
                .filter(models.Meter.timestamp < end)
            for meter_obj in meter_query.all():
                session.delete(meter_obj)

            query = session.query(models.User).filter(
                ~models.User.id.in_(session.query(models.Meter.user_id)
                                    .group_by(models.Meter.user_id)),
                ~models.User.id.in_(session.query(models.AlarmChange.user_id)
                                    .group_by(models.AlarmChange.user_id))
            )
            for user_obj in query.all():
                session.delete(user_obj)

            query = session.query(models.Project)\
                .filter(~models.Project.id.in_(
                    session.query(models.Meter.project_id)
                        .group_by(models.Meter.project_id)),
                        ~models.Project.id.in_(
                            session.query(models.AlarmChange.project_id)
                            .group_by(models.AlarmChange.project_id)),
                        ~models.Project.id.in_(
                            session.query(models.AlarmChange.on_behalf_of)
                            .group_by(models.AlarmChange.on_behalf_of))
                        )
            for project_obj in query.all():
                session.delete(project_obj)

            query = session.query(models.Resource)\
                .filter(~models.Resource.id.in_(
                    session.query(models.Meter.resource_id).group_by(
                        models.Meter.resource_id)))
            for res_obj in query.all():
                session.delete(res_obj)

    def get_users(self, source=None):
        """Return an iterable of user id strings.

        :param source: Optional source filter.
        """
        query = self._get_db_session().query(models.User.id)
        if source is not None:
            query = query.filter(models.User.sources.any(id=source))
        return (x[0] for x in query.all())

    def get_projects(self, source=None):
        """Return an iterable of project id strings.

        :param source: Optional source filter.
        """
        query = self._get_db_session().query(models.Project.id)
        if source:
            query = query.filter(models.Project.sources.any(id=source))
        return (x[0] for x in query.all())

    def get_resources(self, user=None, project=None, source=None,
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

        session = self._get_db_session()

        # (thomasm) We need to get the max timestamp first, since that's the
        # most accurate. We also need to filter down in the subquery to
        # constrain what we have to JOIN on later.
        ts_subquery = session.query(
            models.Meter.resource_id,
            func.max(models.Meter.timestamp).label("max_ts"),
            func.min(models.Meter.timestamp).label("min_ts")
        ).group_by(models.Meter.resource_id)

        # Here are the basic 'eq' operation filters for the sample data.
        for column, value in [(models.Meter.resource_id, resource),
                              (models.Meter.user_id, user),
                              (models.Meter.project_id, project)]:
            if value:
                ts_subquery = ts_subquery.filter(column == value)

        if source:
            ts_subquery = ts_subquery.filter(
                models.Meter.sources.any(id=source))

        if metaquery:
            ts_subquery = apply_metaquery_filter(session,
                                                 ts_subquery,
                                                 metaquery)

        # Here we limit the samples being used to a specific time period,
        # if requested.
        if start_timestamp:
            if start_timestamp_op == 'gt':
                ts_subquery = ts_subquery.filter(
                    models.Meter.timestamp > start_timestamp)
            else:
                ts_subquery = ts_subquery.filter(
                    models.Meter.timestamp >= start_timestamp)
        if end_timestamp:
            if end_timestamp_op == 'le':
                ts_subquery = ts_subquery.filter(
                    models.Meter.timestamp <= end_timestamp)
            else:
                ts_subquery = ts_subquery.filter(
                    models.Meter.timestamp < end_timestamp)
        ts_subquery = ts_subquery.subquery()

        # Now we need to get the max Meter.id out of the leftover results, to
        # break any ties.
        agg_subquery = session.query(
            func.max(models.Meter.id).label("max_id"),
            ts_subquery
        ).filter(
            models.Meter.resource_id == ts_subquery.c.resource_id,
            models.Meter.timestamp == ts_subquery.c.max_ts
        ).group_by(
            ts_subquery.c.resource_id,
            ts_subquery.c.max_ts,
            ts_subquery.c.min_ts
        ).subquery()

        query = session.query(
            models.Meter,
            agg_subquery.c.min_ts,
            agg_subquery.c.max_ts
        ).filter(
            models.Meter.id == agg_subquery.c.max_id
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
            )

    def get_meters(self, user=None, project=None, resource=None, source=None,
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

        session = self._get_db_session()

        # Meter table will store large records and join with resource
        # will be very slow.
        # subquery_meter is used to reduce meter records
        # by selecting a record for each (resource_id, counter_name).
        # max() is used to choice a meter record, so the latest record
        # is selected for each (resource_id, counter_name).
        #
        subquery_meter = session.query(func.max(models.Meter.id).label('id'))\
            .group_by(models.Meter.resource_id,
                      models.Meter.counter_name).subquery()

        # The SQL of query_meter is essentially:
        #
        # SELECT meter.* FROM meter INNER JOIN
        #  (SELECT max(meter.id) AS id FROM meter
        #   GROUP BY meter.resource_id, meter.counter_name) AS anon_2
        # ON meter.id = anon_2.id
        #
        query_meter = session.query(models.Meter).\
            join(subquery_meter, models.Meter.id == subquery_meter.c.id)

        if metaquery:
            query_meter = apply_metaquery_filter(session,
                                                 query_meter,
                                                 metaquery)

        alias_meter = aliased(models.Meter, query_meter.subquery())
        query = session.query(models.Resource, alias_meter).join(
            alias_meter, models.Resource.id == alias_meter.resource_id)

        if user is not None:
            query = query.filter(models.Resource.user_id == user)
        if source is not None:
            query = query.filter(models.Resource.sources.any(id=source))
        if resource:
            query = query.filter(models.Resource.id == resource)
        if project is not None:
            query = query.filter(models.Resource.project_id == project)

        for resource, meter in query.all():
            yield api_models.Meter(
                name=meter.counter_name,
                type=meter.counter_type,
                unit=meter.counter_unit,
                resource_id=resource.id,
                project_id=resource.project_id,
                source=resource.sources[0].id,
                user_id=resource.user_id)

    def _apply_options(self, query, orderby, limit, table):
        query = self._apply_order_by(query, orderby, table)
        if limit is not None:
            query = query.limit(limit)
        return query

    def _retrieve_samples(self, query):
        samples = query.all()

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

    def get_samples(self, sample_filter, limit=None):
        """Return an iterable of api_models.Samples.

        :param sample_filter: Filter.
        :param limit: Maximum number of results to return.
        """
        if limit == 0:
            return []

        table = models.Meter
        session = self._get_db_session()
        query = session.query(table)
        query = make_query_from_filter(session, query, sample_filter,
                                       require_meter=False)

        query = self._apply_options(query,
                                    None,
                                    limit,
                                    table)
        return self._retrieve_samples(query)

    def _retrieve_data(self, filter_expr, orderby, limit, table):
        if limit == 0:
            return []

        session = self._get_db_session()
        query = session.query(table)

        if filter_expr is not None:
            sql_condition = self._transform_expression(filter_expr,
                                                       table)
            query = query.filter(sql_condition)

        query = self._apply_options(query,
                                    orderby,
                                    limit,
                                    table)

        retrieve = {models.Meter: self._retrieve_samples,
                    models.Alarm: self._retrieve_alarms,
                    models.AlarmChange: self._retrieve_alarm_history}
        return retrieve[table](query)

    def query_samples(self, filter_expr=None, orderby=None, limit=None):
        return self._retrieve_data(filter_expr,
                                   orderby,
                                   limit,
                                   models.Meter)

    def _transform_expression(self, expression_tree, table):

        def transform(sub_tree):
            operator = sub_tree.keys()[0]
            nodes = sub_tree.values()[0]
            if operator in self.complex_operators:
                op = self.complex_operators[operator]
                element_list = []
                for node in nodes:
                    element = transform(node)
                    element_list.append(element)
                return op(*element_list)
            else:
                op = self.operators[operator]
                return op(getattr(table, nodes.keys()[0]), nodes.values()[0])

        return transform(expression_tree)

    def _apply_order_by(self, query, orderby, table):

        if orderby is not None:
            for field in orderby:
                ordering_function = self.ordering_functions[field.values()[0]]
                query = query.order_by(ordering_function(
                    getattr(table, field.keys()[0])))
        else:
            query = query.order_by(desc(table.timestamp))
        return query

    def _make_stats_query(self, sample_filter, groupby):
        select = [
            models.Meter.counter_unit.label('unit'),
            func.min(models.Meter.timestamp).label('tsmin'),
            func.max(models.Meter.timestamp).label('tsmax'),
            func.avg(models.Meter.counter_volume).label('avg'),
            func.sum(models.Meter.counter_volume).label('sum'),
            func.min(models.Meter.counter_volume).label('min'),
            func.max(models.Meter.counter_volume).label('max'),
            func.count(models.Meter.counter_volume).label('count'),
        ]

        session = self._get_db_session()

        if groupby:
            group_attributes = [getattr(models.Meter, g) for g in groupby]
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
            q = query.filter(models.Meter.timestamp >= period_start)
            q = q.filter(models.Meter.timestamp < period_end)
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

    def _retrieve_alarms(self, query):
        return (self._row_to_alarm_model(x) for x in query.all())

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

        session = self._get_db_session()
        query = session.query(models.Alarm)
        if name is not None:
            query = query.filter(models.Alarm.name == name)
        if enabled is not None:
            query = query.filter(models.Alarm.enabled == enabled)
        if user is not None:
            query = query.filter(models.Alarm.user_id == user)
        if project is not None:
            query = query.filter(models.Alarm.project_id == project)
        if alarm_id is not None:
            query = query.filter(models.Alarm.id == alarm_id)

        return self._retrieve_alarms(query)

    def create_alarm(self, alarm):
        """Create an alarm.

        :param alarm: The alarm to create.
        """
        session = self._get_db_session()
        with session.begin():
            alarm_row = models.Alarm(id=alarm.alarm_id)
            alarm_row.update(alarm.as_dict())
            session.add(alarm_row)

        return self._row_to_alarm_model(alarm_row)

    def update_alarm(self, alarm):
        """Update an alarm.

        :param alarm: the new Alarm to update
        """
        session = self._get_db_session()
        with session.begin():
            Connection._create_or_update(session, models.User,
                                         alarm.user_id)
            Connection._create_or_update(session, models.Project,
                                         alarm.project_id)
            alarm_row = session.merge(models.Alarm(id=alarm.alarm_id))
            alarm_row.update(alarm.as_dict())

        return self._row_to_alarm_model(alarm_row)

    def delete_alarm(self, alarm_id):
        """Delete an alarm

        :param alarm_id: ID of the alarm to delete
        """
        session = self._get_db_session()
        with session.begin():
            session.query(models.Alarm).filter(
                models.Alarm.id == alarm_id).delete()

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

    def query_alarms(self, filter_expr=None, orderby=None, limit=None):
        """Yields a lists of alarms that match filter
        """
        return self._retrieve_data(filter_expr, orderby, limit, models.Alarm)

    def _retrieve_alarm_history(self, query):
        return (self._row_to_alarm_change_model(x) for x in query.all())

    def query_alarm_history(self, filter_expr=None, orderby=None, limit=None):
        """Return an iterable of model.AlarmChange objects.
        """
        return self._retrieve_data(filter_expr,
                                   orderby,
                                   limit,
                                   models.AlarmChange)

    def get_alarm_changes(self, alarm_id, on_behalf_of,
                          user=None, project=None, type=None,
                          start_timestamp=None, start_timestamp_op=None,
                          end_timestamp=None, end_timestamp_op=None):
        """Yields list of AlarmChanges describing alarm history

        Changes are always sorted in reverse order of occurrence, given
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
        session = self._get_db_session()
        query = session.query(models.AlarmChange)
        query = query.filter(models.AlarmChange.alarm_id == alarm_id)

        if on_behalf_of is not None:
            query = query.filter(
                models.AlarmChange.on_behalf_of == on_behalf_of)
        if user is not None:
            query = query.filter(models.AlarmChange.user_id == user)
        if project is not None:
            query = query.filter(models.AlarmChange.project_id == project)
        if type is not None:
            query = query.filter(models.AlarmChange.type == type)
        if start_timestamp:
            if start_timestamp_op == 'gt':
                query = query.filter(
                    models.AlarmChange.timestamp > start_timestamp)
            else:
                query = query.filter(
                    models.AlarmChange.timestamp >= start_timestamp)
        if end_timestamp:
            if end_timestamp_op == 'le':
                query = query.filter(
                    models.AlarmChange.timestamp <= end_timestamp)
            else:
                query = query.filter(
                    models.AlarmChange.timestamp < end_timestamp)

        query = query.order_by(desc(models.AlarmChange.timestamp))
        return self._retrieve_alarm_history(query)

    def record_alarm_change(self, alarm_change):
        """Record alarm change event.
        """
        session = self._get_db_session()
        with session.begin():
            Connection._create_or_update(session, models.User,
                                         alarm_change['user_id'])
            Connection._create_or_update(session, models.Project,
                                         alarm_change['project_id'])
            Connection._create_or_update(session, models.Project,
                                         alarm_change['on_behalf_of'])
            alarm_change_row = models.AlarmChange(
                event_id=alarm_change['event_id'])
            alarm_change_row.update(alarm_change)
            session.add(alarm_change_row)

    def _get_or_create_trait_type(self, trait_type, data_type, session=None):
        """Find if this trait already exists in the database, and
        if it does not, create a new entry in the trait type table.
        """
        if session is None:
            session = self._get_db_session()
        with session.begin(subtransactions=True):
            tt = session.query(models.TraitType).filter(
                models.TraitType.desc == trait_type,
                models.TraitType.data_type == data_type).first()
            if not tt:
                tt = models.TraitType(trait_type, data_type)
                session.add(tt)
        return tt

    def _make_trait(self, trait_model, event, session=None):
        """Make a new Trait from a Trait model.

        Doesn't flush or add to session.
        """
        trait_type = self._get_or_create_trait_type(trait_model.name,
                                                    trait_model.dtype,
                                                    session)
        value_map = models.Trait._value_map
        values = {'t_string': None, 't_float': None,
                  't_int': None, 't_datetime': None}
        value = trait_model.value
        values[value_map[trait_model.dtype]] = value
        return models.Trait(trait_type, event, **values)

    def _get_or_create_event_type(self, event_type, session=None):
        """Here, we check to see if an event type with the supplied
        name already exists. If not, we create it and return the record.

        This may result in a flush.
        """
        if session is None:
            session = self._get_db_session()
        with session.begin(subtransactions=True):
            et = session.query(models.EventType).filter(
                models.EventType.desc == event_type).first()
            if not et:
                et = models.EventType(event_type)
                session.add(et)
        return et

    def _record_event(self, session, event_model):
        """Store a single Event, including related Traits.
        """
        with session.begin(subtransactions=True):
            event_type = self._get_or_create_event_type(event_model.event_type,
                                                        session=session)

            event = models.Event(event_model.message_id, event_type,
                                 event_model.generated)
            session.add(event)

            new_traits = []
            if event_model.traits:
                for trait in event_model.traits:
                    t = self._make_trait(trait, event, session=session)
                    session.add(t)
                    new_traits.append(t)

        # Note: we don't flush here, explicitly (unless a new trait or event
        # does it). Otherwise, just wait until all the Events are staged.
        return (event, new_traits)

    def record_events(self, event_models):
        """Write the events to SQL database via sqlalchemy.

        :param event_models: a list of model.Event objects.

        Returns a list of events that could not be saved in a
        (reason, event) tuple. Reasons are enumerated in
        storage.model.Event

        Flush when they're all added, unless new EventTypes or
        TraitTypes are added along the way.
        """
        session = self._get_db_session()
        events = []
        problem_events = []
        for event_model in event_models:
            event = None
            try:
                with session.begin():
                    event = self._record_event(session, event_model)
            except dbexc.DBDuplicateEntry:
                problem_events.append((api_models.Event.DUPLICATE,
                                       event_model))
            except Exception as e:
                LOG.exception(_('Failed to record event: %s') % e)
                problem_events.append((api_models.Event.UNKNOWN_PROBLEM,
                                       event_model))
            events.append(event)
        return problem_events

    def get_events(self, event_filter):
        """Return an iterable of model.Event objects.

        :param event_filter: EventFilter instance
        """

        start = event_filter.start_time
        end = event_filter.end_time
        session = self._get_db_session()
        LOG.debug(_("Getting events that match filter: %s") % event_filter)
        with session.begin():
            event_query = session.query(models.Event)

            # Build up the join conditions
            event_join_conditions = [models.EventType.id ==
                                     models.Event.event_type_id]

            if event_filter.event_type:
                event_join_conditions\
                    .append(models.EventType.desc == event_filter.event_type)

            event_query = event_query.join(models.EventType,
                                           and_(*event_join_conditions))

            # Build up the where conditions
            event_filter_conditions = []
            if event_filter.message_id:
                event_filter_conditions\
                    .append(models.Event.message_id == event_filter.message_id)
            if start:
                event_filter_conditions.append(models.Event.generated >= start)
            if end:
                event_filter_conditions.append(models.Event.generated <= end)

            if event_filter_conditions:
                event_query = event_query\
                    .filter(and_(*event_filter_conditions))

            event_models_dict = {}
            if event_filter.traits_filter:
                for trait_filter in event_filter.traits_filter:

                    # Build a sub query that joins Trait to TraitType
                    # where the trait name matches
                    trait_name = trait_filter.pop('key')
                    conditions = [models.Trait.trait_type_id ==
                                  models.TraitType.id,
                                  models.TraitType.desc == trait_name]

                    for key, value in trait_filter.iteritems():
                        if key == 'string':
                            conditions.append(models.Trait.t_string == value)
                        elif key == 'integer':
                            conditions.append(models.Trait.t_int == value)
                        elif key == 'datetime':
                            conditions.append(models.Trait.t_datetime == value)
                        elif key == 'float':
                            conditions.append(models.Trait.t_float == value)

                    trait_query = session.query(models.Trait.event_id)\
                        .join(models.TraitType, and_(*conditions)).subquery()

                    event_query = event_query\
                        .join(trait_query,
                              models.Event.id == trait_query.c.event_id)
            else:
                # If there are no trait filters, grab the events from the db
                query = session.query(models.Event.id,
                                      models.Event.generated,
                                      models.Event.message_id,
                                      models.EventType.desc)\
                    .join(models.EventType,
                          and_(*event_join_conditions))
                if event_filter_conditions:
                    query = query.filter(and_(*event_filter_conditions))
                for (id, generated, message_id, desc) in query.all():
                    event_models_dict[id] = api_models.Event(message_id,
                                                             desc,
                                                             generated,
                                                             [])

            # Build event models for the events
            event_query = event_query.subquery()
            query = session.query(models.Trait)\
                .join(models.TraitType,
                      models.Trait.trait_type_id == models.TraitType.id)\
                .join(event_query, models.Trait.event_id == event_query.c.id)

            # Now convert the sqlalchemy objects back into Models ...
            for trait in query.all():
                event = event_models_dict.get(trait.event_id)
                if not event:
                    event = api_models.Event(
                        trait.event.message_id,
                        trait.event.event_type.desc,
                        trait.event.generated, [])
                    event_models_dict[trait.event_id] = event
                trait_model = api_models.Trait(trait.trait_type.desc,
                                               trait.trait_type.data_type,
                                               trait.get_value())
                event.append_trait(trait_model)

        event_models = event_models_dict.values()
        return sorted(event_models, key=operator.attrgetter('generated'))

    def get_event_types(self):
        """Return all event types as an iterable of strings.
        """

        session = self._get_db_session()
        with session.begin():
            query = session.query(models.EventType.desc)\
                .order_by(models.EventType.desc)
            for name in query.all():
                # The query returns a tuple with one element.
                yield name[0]

    def get_trait_types(self, event_type):
        """Return a dictionary containing the name and data type of
        the trait type. Only trait types for the provided event_type are
        returned.

        :param event_type: the type of the Event
        """
        session = self._get_db_session()

        LOG.debug(_("Get traits for %s") % event_type)
        with session.begin():
            query = (session.query(models.TraitType.desc,
                                   models.TraitType.data_type)
                     .join(models.Trait,
                           models.Trait.trait_type_id ==
                           models.TraitType.id)
                     .join(models.Event,
                           models.Event.id ==
                           models.Trait.event_id)
                     .join(models.EventType,
                           and_(models.EventType.id ==
                                models.Event.id,
                                models.EventType.desc ==
                                event_type))
                     .group_by(models.TraitType.desc,
                               models.TraitType.data_type)
                     .distinct())

            for desc, type in query.all():
                yield {'name': desc, 'data_type': type}

    def get_traits(self, event_type, trait_type=None):
        """Return all trait instances associated with an event_type. If
        trait_type is specified, only return instances of that trait type.

        :param event_type: the type of the Event to filter by
        :param trait_type: the name of the Trait to filter by
        """

        session = self._get_db_session()
        with session.begin():
            trait_type_filters = [models.TraitType.id ==
                                  models.Trait.trait_type_id]
            if trait_type:
                trait_type_filters.append(models.TraitType.desc == trait_type)

            query = (session.query(models.Trait)
                     .join(models.TraitType, and_(*trait_type_filters))
                     .join(models.Event,
                           models.Event.id == models.Trait.event_id)
                     .join(models.EventType,
                           and_(models.EventType.id ==
                                models.Event.event_type_id,
                                models.EventType.desc == event_type)))

            for trait in query.all():
                type = trait.trait_type
                yield api_models.Trait(name=type.desc,
                                       dtype=type.data_type,
                                       value=trait.get_value())
