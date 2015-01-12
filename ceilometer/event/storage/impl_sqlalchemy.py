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
import operator
import os

from oslo.db import exception as dbexc
from oslo.db.sqlalchemy import session as db_session
from oslo_config import cfg
import six
import sqlalchemy as sa

from ceilometer.event.storage import base
from ceilometer.event.storage import models as api_models
from ceilometer.i18n import _
from ceilometer.openstack.common import log
from ceilometer.storage.sqlalchemy import models
from ceilometer.storage.sqlalchemy import utils as sql_utils
from ceilometer import utils

LOG = log.getLogger(__name__)


AVAILABLE_CAPABILITIES = {
    'events': {'query': {'simple': True}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


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
        - Trait
          - trait value
          - { event_id: event -> event.id
              trait_type_id: trait type -> traittype.id
              t_string: string value
              t_float: float value
              t_int: integer value
              t_datetime: timestamp value
              }
        - TraitType
          - trait definition
          - { id: trait id
              desc: description of trait
              data_type: data type (integer that maps to datatype)
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
        # NOTE(gordc): to minimise memory, only import migration when needed
        from oslo.db.sqlalchemy import migration
        path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                            '..', '..', 'storage', 'sqlalchemy',
                            'migrate_repo')
        migration.db_sync(self._engine_facade.get_engine(), path)

    def clear(self):
        engine = self._engine_facade.get_engine()
        for table in reversed(models.Base.metadata.sorted_tables):
            engine.execute(table.delete())
        self._engine_facade._session_maker.close_all()
        engine.dispose()

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

        start = event_filter.start_timestamp
        end = event_filter.end_timestamp
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
                                           sa.and_(*event_join_conditions))

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
                               filter(sa.and_(*event_filter_conditions)))

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
                                        sa.and_(*conditions)).subquery())

                    event_query = (event_query.
                                   join(trait_query, models.Event.id ==
                                        trait_query.c.event_id))
            else:
                # If there are no trait filters, grab the events from the db
                query = (session.query(models.Event.id,
                                       models.Event.generated,
                                       models.Event.message_id,
                                       models.EventType.desc).
                         join(models.EventType,
                              sa.and_(*event_join_conditions)))
                if event_filter_conditions:
                    query = query.filter(sa.and_(*event_filter_conditions))
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
                           sa.and_(models.EventType.id ==
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
                     .join(models.TraitType, sa.and_(*trait_type_filters))
                     .join(models.Event,
                           models.Event.id == models.Trait.event_id)
                     .join(models.EventType,
                           sa.and_(models.EventType.id ==
                                   models.Event.event_type_id,
                                   models.EventType.desc == event_type)))

            for trait in query.all():
                type = trait.trait_type
                yield api_models.Trait(name=type.desc,
                                       dtype=type.data_type,
                                       value=trait.get_value())
