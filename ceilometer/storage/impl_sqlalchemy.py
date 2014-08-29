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

from oslo.config import cfg
from oslo.db import exception as dbexc
from oslo.db.sqlalchemy import migration
from oslo.db.sqlalchemy import session as db_session
from oslo.utils import timeutils
import six
from sqlalchemy import and_
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy.orm import aliased

from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer import storage
from ceilometer.storage import base
from ceilometer.storage import models as api_models
from ceilometer.storage.sqlalchemy import models
from ceilometer.storage.sqlalchemy import utils as sql_utils
from ceilometer import utils

LOG = log.getLogger(__name__)


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
    for k, value in six.iteritems(metaquery):
        key = k[9:]  # strip out 'metadata.' prefix
        try:
            _model = sql_utils.META_TYPE_MAP[type(value)]
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
        self._engine_facade = db_session.EngineFacade(
            url,
            **dict(cfg.CONF.database.items())
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
                obj = (session.query(models.Meter)
                       .filter(models.Meter.name == name)
                       .filter(models.Meter.type == type)
                       .filter(models.Meter.unit == unit).first())
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
                            _model = sql_utils.META_TYPE_MAP[type(v)]
                        except KeyError:
                            LOG.warn(_("Unknown metadata type. Key (%s) will "
                                       "not be queryable."), key)
                        else:
                            session.add(_model(id=sample.id,
                                               meta_key=key,
                                               value=v))

    def clear_expired_metering_data(self, ttl):
        """Clear expired data from the backend storage system.

        Clearing occurs according to the time-to-live.
        :param ttl: Number of seconds to keep records for.
        """

        session = self._engine_facade.get_session()
        with session.begin():
            end = timeutils.utcnow() - datetime.timedelta(seconds=ttl)
            sample_q = (session.query(models.Sample)
                        .filter(models.Sample.timestamp < end))

            sample_subq = sample_q.subquery()
            for table in [models.MetaText, models.MetaBigInt,
                          models.MetaFloat, models.MetaBool]:
                (session.query(table)
                 .join(sample_subq, sample_subq.c.id == table.id)
                 .delete())

            rows = sample_q.delete()
            # remove Meter definitions with no matching samples
            (session.query(models.Meter)
             .filter(~models.Meter.samples.any())
             .delete(synchronize_session='fetch'))
            LOG.info(_("%d samples removed from database"), rows)

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

        s_filter = storage.SampleFilter(user=user,
                                        project=project,
                                        source=source,
                                        start=start_timestamp,
                                        start_timestamp_op=start_timestamp_op,
                                        end=end_timestamp,
                                        end_timestamp_op=end_timestamp_op,
                                        metaquery=metaquery,
                                        resource=resource)

        session = self._engine_facade.get_session()
        # get list of resource_ids
        res_q = session.query(distinct(models.Sample.resource_id))
        res_q = make_query_from_filter(session, res_q, s_filter,
                                       require_meter=False)

        for res_id in res_q.all():
            # get latest Sample
            max_q = (session.query(models.Sample)
                     .filter(models.Sample.resource_id == res_id[0]))
            max_q = make_query_from_filter(session, max_q, s_filter,
                                           require_meter=False)
            max_q = max_q.order_by(models.Sample.timestamp.desc(),
                                   models.Sample.id.desc()).limit(1)

            # get the min timestamp value.
            min_q = (session.query(models.Sample.timestamp)
                     .filter(models.Sample.resource_id == res_id[0]))
            min_q = make_query_from_filter(session, min_q, s_filter,
                                           require_meter=False)
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

        s_filter = storage.SampleFilter(user=user,
                                        project=project,
                                        source=source,
                                        metaquery=metaquery,
                                        resource=resource)

        session = self._engine_facade.get_session()

        # sample_subq is used to reduce sample records
        # by selecting a record for each (resource_id, meter_id).
        # max() is used to choice a sample record, so the latest record
        # is selected for each (resource_id, meter_id).
        sample_subq = (session.query(
                       func.max(models.Sample.id).label('id'))
                       .group_by(models.Sample.meter_id,
                                 models.Sample.resource_id))
        sample_subq = sample_subq.subquery()

        # SELECT sample.* FROM sample INNER JOIN
        #  (SELECT max(sample.id) AS id FROM sample
        #   GROUP BY sample.resource_id, sample.meter_id) AS anon_2
        # ON sample.id = anon_2.id
        query_sample = (session.query(models.MeterSample).
                        join(sample_subq, models.MeterSample.id ==
                        sample_subq.c.id))
        query_sample = make_query_from_filter(session, query_sample, s_filter,
                                              require_meter=False)

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
        transformer = sql_utils.QueryTransformer(table, query)
        transformer.apply_options(None,
                                  limit)
        return self._retrieve_samples(transformer.get_query())

    def query_samples(self, filter_expr=None, orderby=None, limit=None):
        if limit == 0:
            return []

        session = self._engine_facade.get_session()
        query = session.query(models.MeterSample)
        transformer = sql_utils.QueryTransformer(models.MeterSample, query)
        if filter_expr is not None:
            transformer.apply_filter(filter_expr)

        transformer.apply_options(orderby,
                                  limit)
        return self._retrieve_samples(transformer.get_query())

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

        query = (session.query(*select).join(
                 models.Sample, models.Meter.id == models.Sample.meter_id).
                 group_by(models.Meter.unit))

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
        """Return an iterable of api_models.Statistics instances.

        Items are containing meter statistics described by the query
        parameters. The filter must have a meter value set.
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

    def _get_or_create_trait_type(self, trait_type, data_type, session=None):
        """Find if this trait already exists in the database.

        If it does not, create a new entry in the trait type table.
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
        """Check if an event type with the supplied name is already exists.

        If not, we create it and return the record. This may result in a flush.
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
        """Store a single Event, including related Traits."""
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
        return event, new_traits

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
            except dbexc.DBDuplicateEntry as e:
                LOG.exception(_("Failed to record duplicated event: %s") % e)
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
                event_join_conditions.append(models.EventType.desc ==
                                             event_filter.event_type)

            event_query = event_query.join(models.EventType,
                                           and_(*event_join_conditions))

            # Build up the where conditions
            event_filter_conditions = []
            if event_filter.message_id:
                event_filter_conditions.append(models.Event.message_id ==
                                               event_filter.message_id)
            if start:
                event_filter_conditions.append(models.Event.generated >= start)
            if end:
                event_filter_conditions.append(models.Event.generated <= end)

            if event_filter_conditions:
                event_query = (event_query.
                               filter(and_(*event_filter_conditions)))

            event_models_dict = {}
            if event_filter.traits_filter:
                for trait_filter in event_filter.traits_filter:

                    # Build a sub query that joins Trait to TraitType
                    # where the trait name matches
                    trait_name = trait_filter.pop('key')
                    op = trait_filter.pop('op', 'eq')
                    conditions = [models.Trait.trait_type_id ==
                                  models.TraitType.id,
                                  models.TraitType.desc == trait_name]

                    for key, value in six.iteritems(trait_filter):
                        sql_utils.trait_op_condition(conditions,
                                                     key, value, op)

                    trait_query = (session.query(models.Trait.event_id).
                                   join(models.TraitType,
                                        and_(*conditions)).subquery())

                    event_query = (event_query.
                                   join(trait_query, models.Event.id ==
                                        trait_query.c.event_id))
            else:
                # If there are no trait filters, grab the events from the db
                query = (session.query(models.Event.id,
                                       models.Event.generated,
                                       models.Event.message_id,
                                       models.EventType.desc).
                         join(models.EventType, and_(*event_join_conditions)))
                if event_filter_conditions:
                    query = query.filter(and_(*event_filter_conditions))
                for (id_, generated, message_id, desc_) in query.all():
                    event_models_dict[id_] = api_models.Event(message_id,
                                                              desc_,
                                                              generated,
                                                              [])

            # Build event models for the events
            event_query = event_query.subquery()
            query = (session.query(models.Trait).
                     join(models.TraitType, models.Trait.trait_type_id ==
                          models.TraitType.id).
                     join(event_query, models.Trait.event_id ==
                          event_query.c.id))

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
        """Return all event types as an iterable of strings."""

        session = self._engine_facade.get_session()
        with session.begin():
            query = (session.query(models.EventType.desc).
                     order_by(models.EventType.desc))
            for name in query.all():
                # The query returns a tuple with one element.
                yield name[0]

    def get_trait_types(self, event_type):
        """Return a dictionary containing the name and data type of the trait.

        Only trait types for the provided event_type are returned.
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
        """Return all trait instances associated with an event_type.

        If trait_type is specified, only return instances of that trait type.
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
