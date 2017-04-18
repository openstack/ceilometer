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
import hashlib
import os

from oslo_db import api
from oslo_db import exception as dbexc
from oslo_db.sqlalchemy import session as db_session
from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import timeutils
import six
import sqlalchemy as sa
from sqlalchemy import and_
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import cast

import ceilometer
from ceilometer.i18n import _
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
            distinct(getattr(models.Resource, p))
        ).label('cardinality/%s' % p)
    )
)

AVAILABLE_CAPABILITIES = {
    'meters': {'query': {'simple': True,
                         'metadata': True}},
    'resources': {'query': {'simple': True,
                            'metadata': True}},
    'samples': {'query': {'simple': True,
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
            raise ceilometer.NotImplementedError(
                'Query on %(key)s is of %(value)s '
                'type and is not supported' %
                {"key": k, "value": type(value)})
        else:
            meta_alias = aliased(_model)
            on_clause = and_(models.Resource.internal_id == meta_alias.id,
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
            models.Resource.source_id == sample_filter.source)
    if sample_filter.start_timestamp:
        ts_start = sample_filter.start_timestamp
        if sample_filter.start_timestamp_op == 'gt':
            query = query.filter(models.Sample.timestamp > ts_start)
        else:
            query = query.filter(models.Sample.timestamp >= ts_start)
    if sample_filter.end_timestamp:
        ts_end = sample_filter.end_timestamp
        if sample_filter.end_timestamp_op == 'le':
            query = query.filter(models.Sample.timestamp <= ts_end)
        else:
            query = query.filter(models.Sample.timestamp < ts_end)
    if sample_filter.user:
        if sample_filter.user == 'None':
            sample_filter.user = None
        query = query.filter(models.Resource.user_id == sample_filter.user)
    if sample_filter.project:
        if sample_filter.project == 'None':
            sample_filter.project = None
        query = query.filter(
            models.Resource.project_id == sample_filter.project)
    if sample_filter.resource:
        query = query.filter(
            models.Resource.resource_id == sample_filter.resource)
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
          - { id: meter id
              name: meter name
              type: meter type
              unit: meter unit
              }
        - resource
          - resource definition
          - { internal_id: resource id
              resource_id: resource uuid
              user_id: user uuid
              project_id: project uuid
              source_id: source id
              resource_metadata: metadata dictionary
              metadata_hash: metadata dictionary hash
              }
        - sample
          - the raw incoming data
          - { id: sample id
              meter_id: meter id            (->meter.id)
              resource_id: resource id      (->resource.internal_id)
              volume: sample volume
              timestamp: datetime
              recorded_at: datetime
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

    def __init__(self, conf, url):
        super(Connection, self).__init__(conf, url)
        # Set max_retries to 0, since oslo.db in certain cases may attempt
        # to retry making the db connection retried max_retries ^ 2 times
        # in failure case and db reconnection has already been implemented
        # in storage.__init__.get_connection_from_config function
        options = dict(self.conf.database.items())
        options['max_retries'] = 0
        # oslo.db doesn't support options defined by Ceilometer
        for opt in storage.OPTS:
            options.pop(opt.name, None)
        self._engine_facade = db_session.EngineFacade(url, **options)

    def upgrade(self):
        # NOTE(gordc): to minimise memory, only import migration when needed
        from oslo_db.sqlalchemy import migration
        path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                            'sqlalchemy', 'migrate_repo')
        engine = self._engine_facade.get_engine()

        from migrate import exceptions as migrate_exc
        from migrate.versioning import api
        from migrate.versioning import repository

        repo = repository.Repository(path)
        try:
            api.db_version(engine, repo)
        except migrate_exc.DatabaseNotControlledError:
            models.Base.metadata.create_all(engine)
            api.version_control(engine, repo, repo.latest)
        else:
            migration.db_sync(engine, path)

    def clear(self):
        engine = self._engine_facade.get_engine()
        for table in reversed(models.Base.metadata.sorted_tables):
            engine.execute(table.delete())
        engine.dispose()

    @staticmethod
    def _create_meter(conn, name, type, unit):
        # TODO(gordc): implement lru_cache to improve performance
        try:
            meter = models.Meter.__table__
            trans = conn.begin_nested()
            if conn.dialect.name == 'sqlite':
                trans = conn.begin()
            with trans:
                meter_row = conn.execute(
                    sa.select([meter.c.id])
                    .where(sa.and_(meter.c.name == name,
                                   meter.c.type == type,
                                   meter.c.unit == unit))).first()
                meter_id = meter_row[0] if meter_row else None
                if meter_id is None:
                    result = conn.execute(meter.insert(), name=name,
                                          type=type, unit=unit)
                    meter_id = result.inserted_primary_key[0]
        except dbexc.DBDuplicateEntry:
            # retry function to pick up duplicate committed object
            meter_id = Connection._create_meter(conn, name, type, unit)

        return meter_id

    @staticmethod
    def _create_resource(conn, res_id, user_id, project_id, source_id,
                         rmeta):
        # TODO(gordc): implement lru_cache to improve performance
        try:
            res = models.Resource.__table__
            m_hash = jsonutils.dumps(rmeta, sort_keys=True)
            if six.PY3:
                m_hash = m_hash.encode('utf-8')
            m_hash = hashlib.md5(m_hash).hexdigest()
            trans = conn.begin_nested()
            if conn.dialect.name == 'sqlite':
                trans = conn.begin()
            with trans:
                res_row = conn.execute(
                    sa.select([res.c.internal_id])
                    .where(sa.and_(res.c.resource_id == res_id,
                                   res.c.user_id == user_id,
                                   res.c.project_id == project_id,
                                   res.c.source_id == source_id,
                                   res.c.metadata_hash == m_hash))).first()
                internal_id = res_row[0] if res_row else None
                if internal_id is None:
                    result = conn.execute(res.insert(), resource_id=res_id,
                                          user_id=user_id,
                                          project_id=project_id,
                                          source_id=source_id,
                                          resource_metadata=rmeta,
                                          metadata_hash=m_hash)
                    internal_id = result.inserted_primary_key[0]
                    if rmeta and isinstance(rmeta, dict):
                        meta_map = {}
                        for key, v in utils.dict_to_keyval(rmeta):
                            try:
                                _model = sql_utils.META_TYPE_MAP[type(v)]
                                if meta_map.get(_model) is None:
                                    meta_map[_model] = []
                                meta_map[_model].append(
                                    {'id': internal_id, 'meta_key': key,
                                     'value': v})
                            except KeyError:
                                LOG.warning(_("Unknown metadata type. Key "
                                              "(%s) will not be queryable."),
                                            key)
                        for _model in meta_map.keys():
                            conn.execute(_model.__table__.insert(),
                                         meta_map[_model])

        except dbexc.DBDuplicateEntry:
            # retry function to pick up duplicate committed object
            internal_id = Connection._create_resource(
                conn, res_id, user_id, project_id, source_id, rmeta)

        return internal_id

    # FIXME(sileht): use set_defaults to pass cfg.CONF.database.retry_interval
    # and cfg.CONF.database.max_retries to this method when global config
    # have been removed (puting directly cfg.CONF don't work because and copy
    # the default instead of the configured value)
    @api.wrap_db_retry(retry_interval=10, max_retries=10,
                       retry_on_deadlock=True)
    def record_metering_data(self, data):
        """Write the data to the backend storage system.

        :param data: a dictionary such as returned by
                     ceilometer.publisher.utils.meter_message_from_counter
        """
        engine = self._engine_facade.get_engine()
        with engine.begin() as conn:
            # Record the raw data for the sample.
            m_id = self._create_meter(conn,
                                      data['counter_name'],
                                      data['counter_type'],
                                      data['counter_unit'])
            res_id = self._create_resource(conn,
                                           data['resource_id'],
                                           data['user_id'],
                                           data['project_id'],
                                           data['source'],
                                           data['resource_metadata'])
            sample = models.Sample.__table__
            conn.execute(sample.insert(), meter_id=m_id,
                         resource_id=res_id,
                         timestamp=data['timestamp'],
                         volume=data['counter_volume'],
                         message_signature=data['message_signature'],
                         message_id=data['message_id'])

    def clear_expired_metering_data(self, ttl):
        """Clear expired data from the backend storage system.

        Clearing occurs according to the time-to-live.
        :param ttl: Number of seconds to keep records for.
        """
        # Prevent database deadlocks from occurring by
        # using separate transaction for each delete
        session = self._engine_facade.get_session()
        with session.begin():
            end = timeutils.utcnow() - datetime.timedelta(seconds=ttl)
            sample_q = (session.query(models.Sample)
                        .filter(models.Sample.timestamp < end))
            rows = sample_q.delete()
            LOG.info("%d samples removed from database", rows)

        if not self.conf.database.sql_expire_samples_only:
            with session.begin():
                # remove Meter definitions with no matching samples
                (session.query(models.Meter)
                 .filter(~models.Meter.samples.any())
                 .delete(synchronize_session=False))

            with session.begin():
                resource_q = (session.query(models.Resource.internal_id)
                              .filter(~models.Resource.samples.any()))
                # mark resource with no matching samples for delete
                resource_q.update({models.Resource.metadata_hash: "delete_"
                                  + cast(models.Resource.internal_id,
                                         sa.String)},
                                  synchronize_session=False)

            # remove metadata of resources marked for delete
            for table in [models.MetaText, models.MetaBigInt,
                          models.MetaFloat, models.MetaBool]:
                with session.begin():
                    resource_q = (session.query(models.Resource.internal_id)
                                  .filter(models.Resource.metadata_hash
                                          .like('delete_%')))
                    resource_subq = resource_q.subquery()
                    (session.query(table)
                     .filter(table.id.in_(resource_subq))
                     .delete(synchronize_session=False))

            # remove resource marked for delete
            with session.begin():
                resource_q = (session.query(models.Resource.internal_id)
                              .filter(models.Resource.metadata_hash
                                      .like('delete_%')))
                resource_q.delete(synchronize_session=False)
            LOG.info("Expired residual resource and"
                     " meter definition data")

    def get_resources(self, user=None, project=None, source=None,
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None,
                      metaquery=None, resource=None, limit=None):
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
        :param limit: Maximum number of results to return.
        """
        if limit == 0:
            return
        s_filter = storage.SampleFilter(user=user,
                                        project=project,
                                        source=source,
                                        start_timestamp=start_timestamp,
                                        start_timestamp_op=start_timestamp_op,
                                        end_timestamp=end_timestamp,
                                        end_timestamp_op=end_timestamp_op,
                                        metaquery=metaquery,
                                        resource=resource)

        session = self._engine_facade.get_session()
        # get list of resource_ids
        has_timestamp = start_timestamp or end_timestamp
        # NOTE: When sql_expire_samples_only is enabled, there will be some
        #       resources without any sample, in such case we should use inner
        #       join on sample table to avoid wrong result.
        if self.conf.database.sql_expire_samples_only or has_timestamp:
            res_q = session.query(distinct(models.Resource.resource_id)).join(
                models.Sample,
                models.Sample.resource_id == models.Resource.internal_id)
        else:
            res_q = session.query(distinct(models.Resource.resource_id))
        res_q = make_query_from_filter(session, res_q, s_filter,
                                       require_meter=False)
        res_q = res_q.limit(limit) if limit else res_q
        for res_id in res_q.all():

            # get max and min sample timestamp value
            min_max_q = (session.query(func.max(models.Sample.timestamp)
                                       .label('max_timestamp'),
                                       func.min(models.Sample.timestamp)
                                       .label('min_timestamp'))
                                .join(models.Resource,
                                      models.Resource.internal_id ==
                                      models.Sample.resource_id)
                                .filter(models.Resource.resource_id ==
                                        res_id[0]))

            min_max_q = make_query_from_filter(session, min_max_q, s_filter,
                                               require_meter=False)

            min_max = min_max_q.first()

            # get resource details for latest sample
            res_q = (session.query(models.Resource.resource_id,
                                   models.Resource.user_id,
                                   models.Resource.project_id,
                                   models.Resource.source_id,
                                   models.Resource.resource_metadata)
                            .join(models.Sample,
                                  models.Sample.resource_id ==
                                  models.Resource.internal_id)
                            .filter(models.Sample.timestamp ==
                                    min_max.max_timestamp)
                            .filter(models.Resource.resource_id ==
                                    res_id[0])
                            .order_by(models.Sample.id.desc()).limit(1))

            res = res_q.first()

            yield api_models.Resource(
                resource_id=res.resource_id,
                project_id=res.project_id,
                first_sample_timestamp=min_max.min_timestamp,
                last_sample_timestamp=min_max.max_timestamp,
                source=res.source_id,
                user_id=res.user_id,
                metadata=res.resource_metadata
            )

    def get_meters(self, user=None, project=None, resource=None, source=None,
                   metaquery=None, limit=None, unique=False):
        """Return an iterable of api_models.Meter instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional ID of the resource.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param limit: Maximum number of results to return.
        :param unique: If set to true, return only unique meter information.
        """
        if limit == 0:
            return
        s_filter = storage.SampleFilter(user=user,
                                        project=project,
                                        source=source,
                                        metaquery=metaquery,
                                        resource=resource)

        # NOTE(gordc): get latest sample of each meter/resource. we do not
        #              filter here as we want to filter only on latest record.
        session = self._engine_facade.get_session()

        subq = session.query(func.max(models.Sample.id).label('id')).join(
            models.Resource,
            models.Resource.internal_id == models.Sample.resource_id)

        if unique:
            subq = subq.group_by(models.Sample.meter_id)
        else:
            subq = subq.group_by(models.Sample.meter_id,
                                 models.Resource.resource_id)

        if resource:
            subq = subq.filter(models.Resource.resource_id == resource)
        subq = subq.subquery()

        # get meter details for samples.
        query_sample = (session.query(models.Sample.meter_id,
                                      models.Meter.name, models.Meter.type,
                                      models.Meter.unit,
                                      models.Resource.resource_id,
                                      models.Resource.project_id,
                                      models.Resource.source_id,
                                      models.Resource.user_id).join(
            subq, subq.c.id == models.Sample.id)
            .join(models.Meter, models.Meter.id == models.Sample.meter_id)
            .join(models.Resource,
                  models.Resource.internal_id == models.Sample.resource_id))
        query_sample = make_query_from_filter(session, query_sample, s_filter,
                                              require_meter=False)

        query_sample = query_sample.limit(limit) if limit else query_sample

        if unique:
            for row in query_sample.all():
                yield api_models.Meter(
                    name=row.name,
                    type=row.type,
                    unit=row.unit,
                    resource_id=None,
                    project_id=None,
                    source=None,
                    user_id=None)
        else:
            for row in query_sample.all():
                yield api_models.Meter(
                    name=row.name,
                    type=row.type,
                    unit=row.unit,
                    resource_id=row.resource_id,
                    project_id=row.project_id,
                    source=row.source_id,
                    user_id=row.user_id)

    @staticmethod
    def _retrieve_samples(query):
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

        session = self._engine_facade.get_session()
        query = session.query(models.Sample.timestamp,
                              models.Sample.recorded_at,
                              models.Sample.message_id,
                              models.Sample.message_signature,
                              models.Sample.volume.label('counter_volume'),
                              models.Meter.name.label('counter_name'),
                              models.Meter.type.label('counter_type'),
                              models.Meter.unit.label('counter_unit'),
                              models.Resource.source_id,
                              models.Resource.user_id,
                              models.Resource.project_id,
                              models.Resource.resource_metadata,
                              models.Resource.resource_id).join(
            models.Meter, models.Meter.id == models.Sample.meter_id).join(
            models.Resource,
            models.Resource.internal_id == models.Sample.resource_id).order_by(
            models.Sample.timestamp.desc())
        query = make_query_from_filter(session, query, sample_filter,
                                       require_meter=False)
        if limit:
            query = query.limit(limit)
        return self._retrieve_samples(query)

    def query_samples(self, filter_expr=None, orderby=None, limit=None):
        if limit == 0:
            return []

        session = self._engine_facade.get_session()
        engine = self._engine_facade.get_engine()
        query = session.query(models.Sample.timestamp,
                              models.Sample.recorded_at,
                              models.Sample.message_id,
                              models.Sample.message_signature,
                              models.Sample.volume.label('counter_volume'),
                              models.Meter.name.label('counter_name'),
                              models.Meter.type.label('counter_type'),
                              models.Meter.unit.label('counter_unit'),
                              models.Resource.source_id,
                              models.Resource.user_id,
                              models.Resource.project_id,
                              models.Resource.resource_metadata,
                              models.Resource.resource_id).join(
            models.Meter, models.Meter.id == models.Sample.meter_id).join(
            models.Resource,
            models.Resource.internal_id == models.Sample.resource_id)
        transformer = sql_utils.QueryTransformer(models.FullSample, query,
                                                 dialect=engine.dialect.name)
        if filter_expr is not None:
            transformer.apply_filter(filter_expr)

        transformer.apply_options(orderby, limit)
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
                # NOTE(zqfan): We already have checked at API level, but
                # still leave it here in case of directly storage calls.
                msg = _('Invalid aggregation function: %s') % a.func
                raise storage.StorageBadAggregate(msg)

        return functions

    def _make_stats_query(self, sample_filter, groupby, aggregate):

        select = [
            func.min(models.Sample.timestamp).label('tsmin'),
            func.max(models.Sample.timestamp).label('tsmax'),
            models.Meter.unit
        ]
        select.extend(self._get_aggregate_functions(aggregate))

        session = self._engine_facade.get_session()

        if groupby:
            group_attributes = []
            for g in groupby:
                if g != 'resource_metadata.instance_type':
                    group_attributes.append(getattr(models.Resource, g))
                else:
                    group_attributes.append(
                        getattr(models.MetaText, 'value')
                        .label('resource_metadata.instance_type'))

            select.extend(group_attributes)

        query = (
            session.query(*select)
            .join(models.Meter,
                  models.Meter.id == models.Sample.meter_id)
            .join(models.Resource,
                  models.Resource.internal_id == models.Sample.resource_id)
            .group_by(models.Meter.unit))

        if groupby:
            for g in groupby:
                if g == 'resource_metadata.instance_type':
                    query = query.join(
                        models.MetaText,
                        models.Resource.internal_id == models.MetaText.id)
                    query = query.filter(
                        models.MetaText.meta_key == 'instance_type')
            query = query.group_by(*group_attributes)

        return make_query_from_filter(session, query, sample_filter)

    @staticmethod
    def _stats_result_aggregates(result, aggregate):
        stats_args = {}
        if isinstance(result.count, six.integer_types):
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
                if group not in ['user_id', 'project_id', 'resource_id',
                                 'resource_metadata.instance_type']:
                    raise ceilometer.NotImplementedError('Unable to group by '
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

        if not (sample_filter.start_timestamp and sample_filter.end_timestamp):
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
                sample_filter.start_timestamp or res.tsmin,
                sample_filter.end_timestamp or res.tsmax,
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
