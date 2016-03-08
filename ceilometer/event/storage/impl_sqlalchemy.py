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
import os

from oslo_config import cfg
from oslo_db import exception as dbexc
from oslo_db.sqlalchemy import session as db_session
from oslo_log import log
from oslo_utils import timeutils
import sqlalchemy as sa

from ceilometer.event.storage import base
from ceilometer.event.storage import models as api_models
from ceilometer.i18n import _LE, _LI
from ceilometer import storage
from ceilometer.storage.sqlalchemy import models
from ceilometer import utils

LOG = log.getLogger(__name__)


AVAILABLE_CAPABILITIES = {
    'events': {'query': {'simple': True}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


TRAIT_MAPLIST = [(api_models.Trait.NONE_TYPE, models.TraitText),
                 (api_models.Trait.TEXT_TYPE, models.TraitText),
                 (api_models.Trait.INT_TYPE, models.TraitInt),
                 (api_models.Trait.FLOAT_TYPE, models.TraitFloat),
                 (api_models.Trait.DATETIME_TYPE, models.TraitDatetime)]


TRAIT_ID_TO_MODEL = dict((x, y) for x, y in TRAIT_MAPLIST)
TRAIT_MODEL_TO_ID = dict((y, x) for x, y in TRAIT_MAPLIST)


trait_models_dict = {'string': models.TraitText,
                     'integer': models.TraitInt,
                     'datetime': models.TraitDatetime,
                     'float': models.TraitFloat}


def _build_trait_query(session, trait_type, key, value, op='eq'):
    trait_model = trait_models_dict[trait_type]
    op_dict = {'eq': (trait_model.value == value),
               'lt': (trait_model.value < value),
               'le': (trait_model.value <= value),
               'gt': (trait_model.value > value),
               'ge': (trait_model.value >= value),
               'ne': (trait_model.value != value)}
    conditions = [trait_model.key == key, op_dict[op]]
    return (session.query(trait_model.event_id.label('ev_id'))
            .filter(*conditions))


class Connection(base.Connection):
    """Put the event data into a SQLAlchemy database.

    Tables::

        - EventType
          - event definition
          - { id: event type id
              desc: description of event
              }
        - Event
          - event data
          - { id: event id
              message_id: message id
              generated = timestamp of event
              event_type_id = event type -> eventtype.id
              }
        - TraitInt
          - int trait value
          - { event_id: event -> event.id
              key: trait name
              value: integer value
              }
        - TraitDatetime
          - datetime trait value
          - { event_id: event -> event.id
              key: trait name
              value: datetime value
              }
        - TraitText
          - text trait value
          - { event_id: event -> event.id
              key: trait name
              value: text value
              }
        - TraitFloat
          - float trait value
          - { event_id: event -> event.id
              key: trait name
              value: float value
              }

    """
    CAPABILITIES = utils.update_nested(base.Connection.CAPABILITIES,
                                       AVAILABLE_CAPABILITIES)
    STORAGE_CAPABILITIES = utils.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )

    def __init__(self, url):
        # Set max_retries to 0, since oslo.db in certain cases may attempt
        # to retry making the db connection retried max_retries ^ 2 times
        # in failure case and db reconnection has already been implemented
        # in storage.__init__.get_connection_from_config function
        options = dict(cfg.CONF.database.items())
        options['max_retries'] = 0
        # oslo.db doesn't support options defined by Ceilometer
        for opt in storage.OPTS:
            options.pop(opt.name, None)
        self._engine_facade = db_session.EngineFacade(url, **options)

    def upgrade(self):
        # NOTE(gordc): to minimise memory, only import migration when needed
        from oslo_db.sqlalchemy import migration
        path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                            '..', '..', 'storage', 'sqlalchemy',
                            'migrate_repo')
        migration.db_sync(self._engine_facade.get_engine(), path)

    def clear(self):
        engine = self._engine_facade.get_engine()
        for table in reversed(models.Base.metadata.sorted_tables):
            engine.execute(table.delete())
        engine.dispose()

    def _get_or_create_event_type(self, event_type, session=None):
        """Check if an event type with the supplied name is already exists.

        If not, we create it and return the record. This may result in a flush.
        """
        try:
            if session is None:
                session = self._engine_facade.get_session()
            with session.begin(subtransactions=True):
                et = session.query(models.EventType).filter(
                    models.EventType.desc == event_type).first()
                if not et:
                    et = models.EventType(event_type)
                    session.add(et)
        except dbexc.DBDuplicateEntry:
            et = self._get_or_create_event_type(event_type, session)

        return et

    def record_events(self, event_models):
        """Write the events to SQL database via sqlalchemy.

        :param event_models: a list of model.Event objects.
        """
        session = self._engine_facade.get_session()
        error = None
        for event_model in event_models:
            event = None
            try:
                with session.begin():
                    event_type = self._get_or_create_event_type(
                        event_model.event_type, session=session)
                    event = models.Event(event_model.message_id, event_type,
                                         event_model.generated,
                                         event_model.raw)
                    session.add(event)
                    session.flush()

                    if event_model.traits:
                        trait_map = {}
                        for trait in event_model.traits:
                            if trait_map.get(trait.dtype) is None:
                                trait_map[trait.dtype] = []
                            trait_map[trait.dtype].append(
                                {'event_id': event.id,
                                 'key': trait.name,
                                 'value': trait.value})
                        for dtype in trait_map.keys():
                            model = TRAIT_ID_TO_MODEL[dtype]
                            session.execute(model.__table__.insert(),
                                            trait_map[dtype])
            except dbexc.DBDuplicateEntry as e:
                LOG.info(_LI("Duplicate event detected, skipping it: %s") % e)
            except KeyError as e:
                LOG.exception(_LE('Failed to record event: %s') % e)
            except Exception as e:
                LOG.exception(_LE('Failed to record event: %s') % e)
                error = e
        if error:
            raise error

    def get_events(self, event_filter, limit=None):
        """Return an iterable of model.Event objects.

        :param event_filter: EventFilter instance
        """
        if limit == 0:
            return
        session = self._engine_facade.get_session()
        with session.begin():
            # Build up the join conditions
            event_join_conditions = [models.EventType.id ==
                                     models.Event.event_type_id]

            if event_filter.event_type:
                event_join_conditions.append(models.EventType.desc ==
                                             event_filter.event_type)

            # Build up the where conditions
            event_filter_conditions = []
            if event_filter.message_id:
                event_filter_conditions.append(
                    models.Event.message_id == event_filter.message_id)
            if event_filter.start_timestamp:
                event_filter_conditions.append(
                    models.Event.generated >= event_filter.start_timestamp)
            if event_filter.end_timestamp:
                event_filter_conditions.append(
                    models.Event.generated <= event_filter.end_timestamp)

            trait_subq = None
            # Build trait filter
            if event_filter.traits_filter:
                filters = list(event_filter.traits_filter)
                trait_filter = filters.pop()
                key = trait_filter.pop('key')
                op = trait_filter.pop('op', 'eq')
                trait_type, value = list(trait_filter.items())[0]
                trait_subq = _build_trait_query(session, trait_type,
                                                key, value, op)
                for trait_filter in filters:
                    key = trait_filter.pop('key')
                    op = trait_filter.pop('op', 'eq')
                    trait_type, value = list(trait_filter.items())[0]
                    q = _build_trait_query(session, trait_type,
                                           key, value, op)
                    trait_subq = trait_subq.filter(
                        trait_subq.subquery().c.ev_id == q.subquery().c.ev_id)
                trait_subq = trait_subq.subquery()

            query = (session.query(models.Event.id)
                     .join(models.EventType,
                           sa.and_(*event_join_conditions)))
            if trait_subq is not None:
                query = query.join(trait_subq,
                                   trait_subq.c.ev_id == models.Event.id)
            if event_filter.admin_proj:
                no_proj_q = session.query(models.TraitText.event_id).filter(
                    models.TraitText.key == 'project_id')
                admin_q = (session.query(models.TraitText.event_id).filter(
                    ~sa.exists().where(models.TraitText.event_id ==
                                       no_proj_q.subquery().c.event_id)).union(
                    session.query(models.TraitText.event_id).filter(sa.and_(
                        models.TraitText.key == 'project_id',
                        models.TraitText.value == event_filter.admin_proj,
                        models.Event.id == models.TraitText.event_id))))
                query = query.filter(sa.exists().where(
                    models.Event.id ==
                    admin_q.subquery().c.trait_text_event_id))
            if event_filter_conditions:
                query = query.filter(sa.and_(*event_filter_conditions))

            query = query.order_by(models.Event.generated).limit(limit)
            event_list = {}
            # get a list of all events that match filters
            for (id_, generated, message_id,
                 desc, raw) in query.add_columns(
                     models.Event.generated, models.Event.message_id,
                     models.EventType.desc, models.Event.raw).all():
                event_list[id_] = api_models.Event(message_id, desc,
                                                   generated, [], raw)
            # Query all traits related to events.
            # NOTE (gordc): cast is done because pgsql defaults to TEXT when
            #               handling unknown values such as null.
            trait_q = (
                session.query(
                    models.TraitDatetime.event_id,
                    models.TraitDatetime.key, models.TraitDatetime.value,
                    sa.cast(sa.null(), sa.Integer),
                    sa.cast(sa.null(), sa.Float(53)),
                    sa.cast(sa.null(), sa.String(255)))
                .filter(sa.exists().where(
                    models.TraitDatetime.event_id == query.subquery().c.id))
            ).union_all(
                session.query(
                    models.TraitInt.event_id,
                    models.TraitInt.key, sa.null(),
                    models.TraitInt.value, sa.null(), sa.null())
                .filter(sa.exists().where(
                    models.TraitInt.event_id == query.subquery().c.id)),
                session.query(
                    models.TraitFloat.event_id,
                    models.TraitFloat.key, sa.null(), sa.null(),
                    models.TraitFloat.value, sa.null())
                .filter(sa.exists().where(
                    models.TraitFloat.event_id == query.subquery().c.id)),
                session.query(
                    models.TraitText.event_id,
                    models.TraitText.key, sa.null(), sa.null(), sa.null(),
                    models.TraitText.value)
                .filter(sa.exists().where(
                    models.TraitText.event_id == query.subquery().c.id)))

            for id_, key, t_date, t_int, t_float, t_text in (
                    trait_q.order_by(models.TraitDatetime.key)).all():
                if t_int is not None:
                    dtype = api_models.Trait.INT_TYPE
                    val = t_int
                elif t_float is not None:
                    dtype = api_models.Trait.FLOAT_TYPE
                    val = t_float
                elif t_date is not None:
                    dtype = api_models.Trait.DATETIME_TYPE
                    val = t_date
                else:
                    dtype = api_models.Trait.TEXT_TYPE
                    val = t_text

                try:
                    trait_model = api_models.Trait(key, dtype, val)
                    event_list[id_].append_trait(trait_model)
                except KeyError:
                    # NOTE(gordc): this is expected as we do not set REPEATABLE
                    # READ (bug 1506717). if query is run while recording new
                    # event data, trait query may return more data than event
                    # query. they can be safely discarded.
                    pass

            return event_list.values()

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

        with session.begin():
            for trait_model in [models.TraitText, models.TraitInt,
                                models.TraitFloat, models.TraitDatetime]:
                query = (session.query(trait_model.key)
                         .join(models.Event,
                               models.Event.id == trait_model.event_id)
                         .join(models.EventType,
                               sa.and_(models.EventType.id ==
                                       models.Event.event_type_id,
                                       models.EventType.desc == event_type))
                         .distinct())

                dtype = TRAIT_MODEL_TO_ID.get(trait_model)
                for row in query.all():
                    yield {'name': row[0], 'data_type': dtype}

    def get_traits(self, event_type, trait_type=None):
        """Return all trait instances associated with an event_type.

        If trait_type is specified, only return instances of that trait type.
        :param event_type: the type of the Event to filter by
        :param trait_type: the name of the Trait to filter by
        """

        session = self._engine_facade.get_session()
        with session.begin():
            for trait_model in [models.TraitText, models.TraitInt,
                                models.TraitFloat, models.TraitDatetime]:
                query = (session.query(trait_model.key, trait_model.value)
                         .join(models.Event,
                               models.Event.id == trait_model.event_id)
                         .join(models.EventType,
                               sa.and_(models.EventType.id ==
                                       models.Event.event_type_id,
                                       models.EventType.desc == event_type))
                         .order_by(trait_model.key))
                if trait_type:
                    query = query.filter(trait_model.key == trait_type)

                dtype = TRAIT_MODEL_TO_ID.get(trait_model)
                for k, v in query.all():
                    yield api_models.Trait(name=k,
                                           dtype=dtype,
                                           value=v)

    def clear_expired_event_data(self, ttl):
        """Clear expired data from the backend storage system.

        Clearing occurs according to the time-to-live.

        :param ttl: Number of seconds to keep records for.
        """
        session = self._engine_facade.get_session()
        with session.begin():
            end = timeutils.utcnow() - datetime.timedelta(seconds=ttl)
            event_q = (session.query(models.Event.id)
                       .filter(models.Event.generated < end))

            event_subq = event_q.subquery()
            for trait_model in [models.TraitText, models.TraitInt,
                                models.TraitFloat, models.TraitDatetime]:
                (session.query(trait_model)
                 .filter(trait_model.event_id.in_(event_subq))
                 .delete(synchronize_session="fetch"))
            event_rows = event_q.delete()

            # remove EventType and TraitType with no corresponding
            # matching events and traits
            (session.query(models.EventType)
             .filter(~models.EventType.events.any())
             .delete(synchronize_session="fetch"))
            LOG.info(_LI("%d events are removed from database"), event_rows)
