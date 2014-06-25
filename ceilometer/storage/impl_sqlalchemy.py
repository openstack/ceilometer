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

from oslo.config import cfg
from sqlalchemy import and_
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy import not_
from sqlalchemy import or_
from sqlalchemy.orm import aliased

from ceilometer.alarm.storage import models as alarm_api_models
from ceilometer.openstack.common.db import exception as dbexc
from ceilometer.openstack.common.db.sqlalchemy import migration
import ceilometer.openstack.common.db.sqlalchemy.session as sqlalchemy_session
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer import storage
from ceilometer.storage import base
from ceilometer.storage import models as api_models
from ceilometer.storage.sqlalchemy import models
from ceilometer import utils

LOG = log.getLogger(__name__)


META_TYPE_MAP = {bool: models.MetaBool,
                 str: models.MetaText,
                 unicode: models.MetaText,
                 types.NoneType: models.MetaText,
                 int: models.MetaBigInt,
                 long: models.MetaBigInt,
                 float: models.MetaFloat}

STANDARD_AGGREGATES = dict(
    avg=func.avg(models.Sample.volume).label('avg'),
    sum=func.sum(models.Sample.volume).label('sum'),
    min=func.min(models.Sample.volume).label('min'),
    max=func.max(models.Sample.volume).label('max'),
    count=func.count(models.Sample.volume).label('count')
)

UNPARAMETERIZED_AGGREGATES = dict(
    stddev=func.stddev_pop(models.Sample.volume).label('stddev')
)

PARAMETERIZED_AGGREGATES = dict(
    validate=dict(
        cardinality=lambda p: p in ['resource_id', 'user_id', 'project_id']
    ),
    compute=dict(
        cardinality=lambda p: func.count(
            distinct(getattr(models.Sample, p))
        ).label('cardinality/%s' % p)
    )
)

AVAILABLE_CAPABILITIES = {
    'meters': {'query': {'simple': True,
                         'metadata': True}},
    'resources': {'query': {'simple': True,
                            'metadata': True}},
    'samples': {'pagination': True,
                'groupby': True,
                'query': {'simple': True,
                          'metadata': True,
                          'complex': True}},
    'statistics': {'groupby': True,
                   'query': {'simple': True,
                             'metadata': True},
                   'aggregation': {'standard': True,
                                   'selectable': {
                                       'max': True,
                                       'min': True,
                                       'sum': True,
                                       'avg': True,
                                       'count': True,
                                       'stddev': True,
                                       'cardinality': True}}
                   },
    'alarms': {'query': {'simple': True,
                         'complex': True},
               'history': {'query': {'simple': True,
                                     'complex': True}}},
    'events': {'query': {'simple': True}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


def apply_metaquery_filter(session, query, metaquery):
    """Apply provided metaquery filter to existing query.

    :param session: session used for original query
    :param query: Query instance
    :param metaquery: dict with metadata to match on.
    """
    for k, value in metaquery.iteritems():
        key = k[9:]  # strip out 'metadata.' prefix
        try:
            _model = META_TYPE_MAP[type(value)]
        except KeyError:
            raise NotImplementedError('Query on %(key)s is of %(value)s '
                                      'type and is not supported' %
                                      {"key": k, "value": type(value)})
        else:
            meta_alias = aliased(_model)
            on_clause = and_(models.Sample.id == meta_alias.id,
                             meta_alias.meta_key == key)
            # outer join is needed to support metaquery
            # with or operator on non existent metadata field
            # see: test_query_non_existing_metadata_with_result
            # test case.
            query = query.outerjoin(meta_alias, on_clause)
            query = query.filter(meta_alias.value == value)

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
        query = query.filter(models.Meter.name == sample_filter.meter)
    elif require_meter:
        raise RuntimeError('Missing required meter specifier')
    if sample_filter.source:
        query = query.filter(
            models.Sample.source_id == sample_filter.source)
    if sample_filter.start:
        ts_start = sample_filter.start
        if sample_filter.start_timestamp_op == 'gt':
            query = query.filter(models.Sample.timestamp > ts_start)
        else:
            query = query.filter(models.Sample.timestamp >= ts_start)
    if sample_filter.end:
        ts_end = sample_filter.end
        if sample_filter.end_timestamp_op == 'le':
            query = query.filter(models.Sample.timestamp <= ts_end)
        else:
            query = query.filter(models.Sample.timestamp < ts_end)
    if sample_filter.user:
        query = query.filter(models.Sample.user_id == sample_filter.user)
    if sample_filter.project:
        query = query.filter(
            models.Sample.project_id == sample_filter.project)
    if sample_filter.resource:
        query = query.filter(
            models.Sample.resource_id == sample_filter.resource)
    if sample_filter.message_id:
        query = query.filter(
            models.Sample.message_id == sample_filter.message_id)

    if sample_filter.metaquery:
        query = apply_metaquery_filter(session, query,
                                       sample_filter.metaquery)

    return query


class Connection(base.Connection):
    """Put the data into a SQLAlchemy database.

    Tables::

        - meter
          - meter definition
          - { id: meter def id
              name: meter name
              type: meter type
              unit: meter unit
              }
        - sample
          - the raw incoming data
          - { id: sample id
              meter_id: meter id            (->meter.id)
              user_id: user uuid
              project_id: project uuid
              resource_id: resource uuid
              source_id: source id
              resource_metadata: metadata dictionaries
              volume: sample volume
              timestamp: datetime
              message_signature: message signature
              message_id: message uuid
              }
    """
    CAPABILITIES = utils.update_nested(base.Connection.CAPABILITIES,
                                       AVAILABLE_CAPABILITIES)
    STORAGE_CAPABILITIES = utils.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )

    def __init__(self, url):
        self._engine_facade = sqlalchemy_session.EngineFacade.from_config(
            url,
            cfg.CONF  # TODO(Alexei_987) Remove access to global CONF object
        )

    def upgrade(self):
        path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                            'sqlalchemy', 'migrate_repo')
        migration.db_sync(self._engine_facade.get_engine(), path)

    def clear(self):
        engine = self._engine_facade.get_engine()
        for table in reversed(models.Base.metadata.sorted_tables):
            engine.execute(table.delete())
        self._engine_facade._session_maker.close_all()
        engine.dispose()

    @staticmethod
    def _create_meter(session, name, type, unit):
        try:
            nested = session.connection().dialect.name != 'sqlite'
            with session.begin(nested=nested,
                               subtransactions=not nested):
                obj = session.query(models.Meter)\
                    .filter(models.Meter.name == name)\
                    .filter(models.Meter.type == type)\
                    .filter(models.Meter.unit == unit).first()
                if obj is None:
                    obj = models.Meter(name=name, type=type, unit=unit)
                    session.add(obj)
        except dbexc.DBDuplicateEntry:
            # retry function to pick up duplicate committed object
            obj = Connection._create_meter(session, name, type, unit)

        return obj

    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.meter.meter_message_from_counter
        """
        session = self._engine_facade.get_session()
        with session.begin():
            # Record the raw data for the sample.
            rmetadata = data['resource_metadata']
            meter = self._create_meter(session,
                                       data['counter_name'],
                                       data['counter_type'],
                                       data['counter_unit'])
            sample = models.Sample(meter_id=meter.id)
            session.add(sample)
            sample.resource_id = data['resource_id']
            sample.project_id = data['project_id']
            sample.user_id = data['user_id']
            sample.timestamp = data['timestamp']
            sample.resource_metadata = rmetadata
            sample.volume = data['counter_volume']
            sample.message_signature = data['message_signature']
            sample.message_id = data['message_id']
            sample.source_id = data['source']
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
                            session.add(_model(id=sample.id,
                                               meta_key=key,
                                               value=v))

    def clear_expired_metering_data(self, ttl):
        """Clear expired data from the backend storage system according to the
        time-to-live.

        :param ttl: Number of seconds to keep records for.

        """

        session = self._engine_facade.get_session()
        with session.begin():
            end = timeutils.utcnow() - datetime.timedelta(seconds=ttl)
            sample_query = session.query(models.Sample)\
                .filter(models.Sample.timestamp < end)
            for sample_obj in sample_query.all():
                session.delete(sample_obj)

    def get_resources(self, user=None, project=None, source=None,
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None,
                      metaquery=None, resource=None, pagination=None):
        """Return an iterable of api_models.Resource instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param source: Optional source filter.
        :param start_timestamp: Optional modified timestamp start range.
        :param start_timestamp_op: Optional start time operator, like gt, ge.
        :param end_timestamp: Optional modified timestamp end range.
        :param end_timestamp_op: Optional end time operator, like lt, le.
        :param metaquery: Optional dict with metadata to match on.
        :param resource: Optional resource filter.
        :param pagination: Optional pagination query.
        """
        if pagination:
            raise NotImplementedError('Pagination not implemented')

        metaquery = metaquery or {}

        def _apply_filters(query):
            # TODO(gordc) this should be merged with make_query_from_filter
            for column, value in [(models.Sample.resource_id, resource),
                                  (models.Sample.user_id, user),
                                  (models.Sample.project_id, project),
                                  (models.Sample.source_id, source)]:
                if value:
                    query = query.filter(column == value)
            if metaquery:
                query = apply_metaquery_filter(session, query, metaquery)
            if start_timestamp:
                if start_timestamp_op == 'gt':
                    query = query.filter(
                        models.Sample.timestamp > start_timestamp)
                else:
                    query = query.filter(
                        models.Sample.timestamp >= start_timestamp)
            if end_timestamp:
                if end_timestamp_op == 'le':
                    query = query.filter(
                        models.Sample.timestamp <= end_timestamp)
                else:
                    query = query.filter(
                        models.Sample.timestamp < end_timestamp)
            return query

        session = self._engine_facade.get_session()
        # get list of resource_ids
        res_q = session.query(distinct(models.Sample.resource_id))
        res_q = _apply_filters(res_q)

        for res_id in res_q.all():
            # get latest Sample
            max_q = session.query(models.Sample)\
                .filter(models.Sample.resource_id == res_id[0])
            max_q = _apply_filters(max_q)
            max_q = max_q.order_by(models.Sample.timestamp.desc(),
                                   models.Sample.id.desc()).limit(1)

            # get the min timestamp value.
            min_q = session.query(models.Sample.timestamp)\
                .filter(models.Sample.resource_id == res_id[0])
            min_q = _apply_filters(min_q)
            min_q = min_q.order_by(models.Sample.timestamp.asc()).limit(1)

            sample = max_q.first()
            if sample:
                yield api_models.Resource(
                    resource_id=sample.resource_id,
                    project_id=sample.project_id,
                    first_sample_timestamp=min_q.first().timestamp,
                    last_sample_timestamp=sample.timestamp,
                    source=sample.source_id,
                    user_id=sample.user_id,
                    metadata=sample.resource_metadata
                )

    def get_meters(self, user=None, project=None, resource=None, source=None,
                   metaquery=None, pagination=None):
        """Return an iterable of api_models.Meter instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional ID of the resource.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param pagination: Optional pagination query.
        """

        if pagination:
            raise NotImplementedError('Pagination not implemented')

        metaquery = metaquery or {}

        def _apply_filters(query):
            # TODO(gordc) this should be merged with make_query_from_filter
            for column, value in [(models.Sample.resource_id, resource),
                                  (models.Sample.user_id, user),
                                  (models.Sample.project_id, project),
                                  (models.Sample.source_id, source)]:
                if value:
                    query = query.filter(column == value)
            if metaquery:
                query = apply_metaquery_filter(session, query, metaquery)
            return query

        session = self._engine_facade.get_session()

        # sample_subq is used to reduce sample records
        # by selecting a record for each (resource_id, meter_id).
        # max() is used to choice a sample record, so the latest record
        # is selected for each (resource_id, meter_id).
        sample_subq = session.query(
            func.max(models.Sample.id).label('id'))\
            .group_by(models.Sample.meter_id, models.Sample.resource_id)
        sample_subq = sample_subq.subquery()

        # SELECT sample.* FROM sample INNER JOIN
        #  (SELECT max(sample.id) AS id FROM sample
        #   GROUP BY sample.resource_id, sample.meter_id) AS anon_2
        # ON sample.id = anon_2.id
        query_sample = session.query(models.MeterSample).\
            join(sample_subq, models.MeterSample.id == sample_subq.c.id)
        query_sample = _apply_filters(query_sample)

        for sample in query_sample.all():
            yield api_models.Meter(
                name=sample.counter_name,
                type=sample.counter_type,
                unit=sample.counter_unit,
                resource_id=sample.resource_id,
                project_id=sample.project_id,
                source=sample.source_id,
                user_id=sample.user_id)

    def _retrieve_samples(self, query):
        samples = query.all()

        for s in samples:
            # Remove the id generated by the database when
            # the sample was inserted. It is an implementation
            # detail that should not leak outside of the driver.
            yield api_models.Sample(
                source=s.source_id,
                counter_name=s.counter_name,
                counter_type=s.counter_type,
                counter_unit=s.counter_unit,
                counter_volume=s.counter_volume,
                user_id=s.user_id,
                project_id=s.project_id,
                resource_id=s.resource_id,
                timestamp=s.timestamp,
                recorded_at=s.recorded_at,
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

        table = models.MeterSample
        session = self._engine_facade.get_session()
        query = session.query(table)
        query = make_query_from_filter(session, query, sample_filter,
                                       require_meter=False)
        transformer = QueryTransformer(table, query)
        transformer.apply_options(None,
                                  limit)
        return self._retrieve_samples(transformer.get_query())

    def _retrieve_data(self, filter_expr, orderby, limit, table):
        if limit == 0:
            return []

        session = self._engine_facade.get_session()
        query = session.query(table)
        transformer = QueryTransformer(table, query)
        if filter_expr is not None:
            transformer.apply_filter(filter_expr)

        transformer.apply_options(orderby,
                                  limit)

        retrieve = {models.MeterSample: self._retrieve_samples,
                    models.Alarm: self._retrieve_alarms,
                    models.AlarmChange: self._retrieve_alarm_history}
        return retrieve[table](transformer.get_query())

    def query_samples(self, filter_expr=None, orderby=None, limit=None):
        return self._retrieve_data(filter_expr,
                                   orderby,
                                   limit,
                                   models.MeterSample)

    @staticmethod
    def _get_aggregate_functions(aggregate):
        if not aggregate:
            return [f for f in STANDARD_AGGREGATES.values()]

        functions = []

        for a in aggregate:
            if a.func in STANDARD_AGGREGATES:
                functions.append(STANDARD_AGGREGATES[a.func])
            elif a.func in UNPARAMETERIZED_AGGREGATES:
                functions.append(UNPARAMETERIZED_AGGREGATES[a.func])
            elif a.func in PARAMETERIZED_AGGREGATES['compute']:
                validate = PARAMETERIZED_AGGREGATES['validate'].get(a.func)
                if not (validate and validate(a.param)):
                    raise storage.StorageBadAggregate('Bad aggregate: %s.%s'
                                                      % (a.func, a.param))
                compute = PARAMETERIZED_AGGREGATES['compute'][a.func]
                functions.append(compute(a.param))
            else:
                raise NotImplementedError('Selectable aggregate function %s'
                                          ' is not supported' % a.func)

        return functions

    def _make_stats_query(self, sample_filter, groupby, aggregate):

        select = [
            models.Meter.unit,
            func.min(models.Sample.timestamp).label('tsmin'),
            func.max(models.Sample.timestamp).label('tsmax'),
        ]

        select.extend(self._get_aggregate_functions(aggregate))

        session = self._engine_facade.get_session()

        if groupby:
            group_attributes = [getattr(models.Sample, g) for g in groupby]
            select.extend(group_attributes)

        query = session.query(*select).filter(
            models.Meter.id == models.Sample.meter_id)\
            .group_by(models.Meter.unit)

        if groupby:
            query = query.group_by(*group_attributes)

        return make_query_from_filter(session, query, sample_filter)

    @staticmethod
    def _stats_result_aggregates(result, aggregate):
        stats_args = {}
        if isinstance(result.count, (int, long)):
            stats_args['count'] = result.count
        for attr in ['min', 'max', 'sum', 'avg']:
            if hasattr(result, attr):
                stats_args[attr] = getattr(result, attr)
        if aggregate:
            stats_args['aggregate'] = {}
            for a in aggregate:
                key = '%s%s' % (a.func, '/%s' % a.param if a.param else '')
                stats_args['aggregate'][key] = getattr(result, key)
        return stats_args

    @staticmethod
    def _stats_result_to_model(result, period, period_start,
                               period_end, groupby, aggregate):
        stats_args = Connection._stats_result_aggregates(result, aggregate)
        stats_args['unit'] = result.unit
        duration = (timeutils.delta_seconds(result.tsmin, result.tsmax)
                    if result.tsmin is not None and result.tsmax is not None
                    else None)
        stats_args['duration'] = duration
        stats_args['duration_start'] = result.tsmin
        stats_args['duration_end'] = result.tsmax
        stats_args['period'] = period
        stats_args['period_start'] = period_start
        stats_args['period_end'] = period_end
        stats_args['groupby'] = (dict(
            (g, getattr(result, g)) for g in groupby) if groupby else None)
        return api_models.Statistics(**stats_args)

    def get_meter_statistics(self, sample_filter, period=None, groupby=None,
                             aggregate=None):
        """Return an iterable of api_models.Statistics instances containing
        meter statistics described by the query parameters.

        The filter must have a meter value set.

        """
        if groupby:
            for group in groupby:
                if group not in ['user_id', 'project_id', 'resource_id']:
                    raise NotImplementedError('Unable to group by '
                                              'these fields')

        if not period:
            for res in self._make_stats_query(sample_filter,
                                              groupby,
                                              aggregate):
                if res.count:
                    yield self._stats_result_to_model(res, 0,
                                                      res.tsmin, res.tsmax,
                                                      groupby,
                                                      aggregate)
            return

        if not sample_filter.start or not sample_filter.end:
            res = self._make_stats_query(sample_filter,
                                         None,
                                         aggregate).first()
            if not res:
                # NOTE(liusheng):The 'res' may be NoneType, because no
                # sample has found with sample filter(s).
                return

        query = self._make_stats_query(sample_filter, groupby, aggregate)
        # HACK(jd) This is an awful method to compute stats by period, but
        # since we're trying to be SQL agnostic we have to write portable
        # code, so here it is, admire! We're going to do one request to get
        # stats by period. We would like to use GROUP BY, but there's no
        # portable way to manipulate timestamp in SQL, so we can't.
        for period_start, period_end in base.iter_period(
                sample_filter.start or res.tsmin,
                sample_filter.end or res.tsmax,
                period):
            q = query.filter(models.Sample.timestamp >= period_start)
            q = q.filter(models.Sample.timestamp < period_end)
            for r in q.all():
                if r.count:
                    yield self._stats_result_to_model(
                        result=r,
                        period=int(timeutils.delta_seconds(period_start,
                                                           period_end)),
                        period_start=period_start,
                        period_end=period_end,
                        groupby=groupby,
                        aggregate=aggregate
                    )

    @staticmethod
    def _row_to_alarm_model(row):
        return alarm_api_models.Alarm(alarm_id=row.alarm_id,
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
                                      insufficient_data_actions=(
                                          row.insufficient_data_actions),
                                      rule=row.rule,
                                      time_constraints=row.time_constraints,
                                      repeat_actions=row.repeat_actions)

    def _retrieve_alarms(self, query):
        return (self._row_to_alarm_model(x) for x in query.all())

    def get_alarms(self, name=None, user=None, state=None, meter=None,
                   project=None, enabled=None, alarm_id=None, pagination=None):
        """Yields a lists of alarms that match filters
        :param user: Optional ID for user that owns the resource.
        :param state: Optional string for alarm state.
        :param meter: Optional string for alarms associated with meter.
        :param project: Optional ID for project that owns the resource.
        :param enabled: Optional boolean to list disable alarm.
        :param alarm_id: Optional alarm_id to return one alarm.
        :param pagination: Optional pagination query.
        """

        if pagination:
            raise NotImplementedError('Pagination not implemented')

        session = self._engine_facade.get_session()
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
            query = query.filter(models.Alarm.alarm_id == alarm_id)
        if state is not None:
            query = query.filter(models.Alarm.state == state)

        alarms = self._retrieve_alarms(query)

        # TODO(cmart): improve this by using sqlalchemy.func factory
        if meter is not None:
            alarms = filter(lambda row:
                            row.rule.get('meter_name', None) == meter,
                            alarms)

        return alarms

    def create_alarm(self, alarm):
        """Create an alarm.

        :param alarm: The alarm to create.
        """
        session = self._engine_facade.get_session()
        with session.begin():
            alarm_row = models.Alarm(alarm_id=alarm.alarm_id)
            alarm_row.update(alarm.as_dict())
            session.add(alarm_row)

        return self._row_to_alarm_model(alarm_row)

    def update_alarm(self, alarm):
        """Update an alarm.

        :param alarm: the new Alarm to update
        """
        session = self._engine_facade.get_session()
        with session.begin():
            alarm_row = session.merge(models.Alarm(alarm_id=alarm.alarm_id))
            alarm_row.update(alarm.as_dict())

        return self._row_to_alarm_model(alarm_row)

    def delete_alarm(self, alarm_id):
        """Delete an alarm

        :param alarm_id: ID of the alarm to delete
        """
        session = self._engine_facade.get_session()
        with session.begin():
            session.query(models.Alarm).filter(
                models.Alarm.alarm_id == alarm_id).delete()

    @staticmethod
    def _row_to_alarm_change_model(row):
        return alarm_api_models.AlarmChange(event_id=row.event_id,
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
        session = self._engine_facade.get_session()
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
        session = self._engine_facade.get_session()
        with session.begin():
            alarm_change_row = models.AlarmChange(
                event_id=alarm_change['event_id'])
            alarm_change_row.update(alarm_change)
            session.add(alarm_change_row)

    def _get_or_create_trait_type(self, trait_type, data_type, session=None):
        """Find if this trait already exists in the database, and
        if it does not, create a new entry in the trait type table.
        """
        if session is None:
            session = self._engine_facade.get_session()
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
            session = self._engine_facade.get_session()
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
        session = self._engine_facade.get_session()
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
        session = self._engine_facade.get_session()
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
                for (id_, generated, message_id, desc_) in query.all():
                    event_models_dict[id_] = api_models.Event(message_id,
                                                              desc_,
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

        session = self._engine_facade.get_session()
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
        session = self._engine_facade.get_session()

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

            for desc_, dtype in query.all():
                yield {'name': desc_, 'data_type': dtype}

    def get_traits(self, event_type, trait_type=None):
        """Return all trait instances associated with an event_type. If
        trait_type is specified, only return instances of that trait type.

        :param event_type: the type of the Event to filter by
        :param trait_type: the name of the Trait to filter by
        """

        session = self._engine_facade.get_session()
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


class QueryTransformer(object):
    operators = {"=": operator.eq,
                 "<": operator.lt,
                 ">": operator.gt,
                 "<=": operator.le,
                 "=<": operator.le,
                 ">=": operator.ge,
                 "=>": operator.ge,
                 "!=": operator.ne,
                 "in": lambda field_name, values: field_name.in_(values)}

    complex_operators = {"or": or_,
                         "and": and_,
                         "not": not_}

    ordering_functions = {"asc": asc,
                          "desc": desc}

    def __init__(self, table, query):
        self.table = table
        self.query = query

    def _handle_complex_op(self, complex_op, nodes):
        op = self.complex_operators[complex_op]
        if op == not_:
            nodes = [nodes]
        element_list = []
        for node in nodes:
            element = self._transform(node)
            element_list.append(element)
        return op(*element_list)

    def _handle_simple_op(self, simple_op, nodes):
        op = self.operators[simple_op]
        field_name = nodes.keys()[0]
        value = nodes.values()[0]
        if field_name.startswith('resource_metadata.'):
            return self._handle_metadata(op, field_name, value)
        else:
            return op(getattr(self.table, field_name), value)

    def _handle_metadata(self, op, field_name, value):
        if op == self.operators["in"]:
            raise NotImplementedError('Metadata query with in '
                                      'operator is not implemented')

        field_name = field_name[len('resource_metadata.'):]
        meta_table = META_TYPE_MAP[type(value)]
        meta_alias = aliased(meta_table)
        on_clause = and_(self.table.id == meta_alias.id,
                         meta_alias.meta_key == field_name)
        # outer join is needed to support metaquery
        # with or operator on non existent metadata field
        # see: test_query_non_existing_metadata_with_result
        # test case.
        self.query = self.query.outerjoin(meta_alias, on_clause)
        return op(meta_alias.value, value)

    def _transform(self, sub_tree):
        operator = sub_tree.keys()[0]
        nodes = sub_tree.values()[0]
        if operator in self.complex_operators:
            return self._handle_complex_op(operator, nodes)
        else:
            return self._handle_simple_op(operator, nodes)

    def apply_filter(self, expression_tree):
        condition = self._transform(expression_tree)
        self.query = self.query.filter(condition)

    def apply_options(self, orderby, limit):
        self._apply_order_by(orderby)
        if limit is not None:
            self.query = self.query.limit(limit)

    def _apply_order_by(self, orderby):
        if orderby is not None:
            for field in orderby:
                ordering_function = self.ordering_functions[field.values()[0]]
                self.query = self.query.order_by(ordering_function(
                    getattr(self.table, field.keys()[0])))
        else:
            self.query = self.query.order_by(desc(self.table.timestamp))

    def get_query(self):
        return self.query
