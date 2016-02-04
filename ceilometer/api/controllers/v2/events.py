#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 IBM Corp.
# Copyright 2013 eNovance <licensing@enovance.com>
# Copyright Ericsson AB 2013. All rights reserved
# Copyright 2014 Hewlett-Packard Company
# Copyright 2015 Huawei Technologies Co., Ltd.
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

import datetime

from oslo_log import log
import pecan
from pecan import rest
import six
import wsme
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from ceilometer.api.controllers.v2 import base
from ceilometer.api.controllers.v2 import utils as v2_utils
from ceilometer.api import rbac
from ceilometer.event.storage import models as event_models
from ceilometer.i18n import _
from ceilometer import storage

LOG = log.getLogger(__name__)


class TraitDescription(base.Base):
    """A description of a trait, with no associated value."""

    type = wtypes.text
    "the data type, defaults to string"

    name = wtypes.text
    "the name of the trait"

    @classmethod
    def sample(cls):
        return cls(name='service',
                   type='string'
                   )


class EventQuery(base.Query):
    """Query arguments for Event Queries."""

    _supported_types = ['integer', 'float', 'string', 'datetime']

    type = wsme.wsattr(wtypes.text, default='string')
    "the type of the trait filter, defaults to string"

    def __repr__(self):
        # for logging calls
        return '<EventQuery %r %s %r %s>' % (self.field,
                                             self.op,
                                             self._get_value_as_type(),
                                             self.type)

    @classmethod
    def sample(cls):
        return cls(field="event_type",
                   type="string",
                   op="eq",
                   value="compute.instance.create.start")


class Trait(base.Base):
    """A Trait associated with an event."""

    name = wtypes.text
    "The name of the trait"

    value = wtypes.text
    "the value of the trait"

    type = wtypes.text
    "the type of the trait (string, integer, float or datetime)"

    @staticmethod
    def _convert_storage_trait(trait):
        """Helper method to convert a storage model into an API trait instance.

        If an API trait instance is passed in, just return it.
        """
        if isinstance(trait, Trait):
            return trait
        value = (six.text_type(trait.value)
                 if not trait.dtype == event_models.Trait.DATETIME_TYPE
                 else trait.value.isoformat())
        trait_type = event_models.Trait.get_name_by_type(trait.dtype)
        return Trait(name=trait.name, type=trait_type, value=value)

    @classmethod
    def sample(cls):
        return cls(name='service',
                   type='string',
                   value='compute.hostname'
                   )


class Event(base.Base):
    """A System event."""

    message_id = wtypes.text
    "The message ID for the notification"

    event_type = wtypes.text
    "The type of the event"

    _traits = None

    def get_traits(self):
        return self._traits

    def set_traits(self, traits):
        self._traits = map(Trait._convert_storage_trait, traits)

    traits = wsme.wsproperty(wtypes.ArrayType(Trait),
                             get_traits,
                             set_traits)
    "Event specific properties"

    generated = datetime.datetime
    "The time the event occurred"

    raw = base.JsonType()
    "The raw copy of notification"

    @classmethod
    def sample(cls):
        return cls(
            event_type='compute.instance.update',
            generated=datetime.datetime(2015, 1, 1, 12, 30, 59, 123456),
            message_id='94834db1-8f1b-404d-b2ec-c35901f1b7f0',
            traits={
                Trait(name='request_id',
                      value='req-4e2d67b8-31a4-48af-bb2f-9df72a353a72'),
                Trait(name='service',
                      value='conductor.tem-devstack-01'),
                Trait(name='tenant_id',
                      value='7f13f2b17917463b9ee21aa92c4b36d6')
            },
            raw={'status': {'nested': 'started'}}
        )


def _build_rbac_query_filters():
    filters = {'t_filter': [], 'admin_proj': None}
    # Returns user_id, proj_id for non-admins
    user_id, proj_id = rbac.get_limited_to(pecan.request.headers)
    # If non-admin, filter events by user and project
    if user_id and proj_id:
        filters['t_filter'].append({"key": "project_id", "string": proj_id,
                                    "op": "eq"})
        filters['t_filter'].append({"key": "user_id", "string": user_id,
                                    "op": "eq"})
    elif not user_id and not proj_id:
        filters['admin_proj'] = pecan.request.headers.get('X-Project-Id')
    return filters


def _event_query_to_event_filter(q):
    evt_model_filter = {
        'event_type': None,
        'message_id': None,
        'start_timestamp': None,
        'end_timestamp': None
    }
    filters = _build_rbac_query_filters()
    traits_filter = filters['t_filter']
    admin_proj = filters['admin_proj']

    for i in q:
        if not i.op:
            i.op = 'eq'
        elif i.op not in base.operation_kind:
            error = (_('Operator %(operator)s is not supported. The supported'
                       ' operators are: %(supported)s') %
                     {'operator': i.op, 'supported': base.operation_kind})
            raise base.ClientSideError(error)
        if i.field in evt_model_filter:
            if i.op != 'eq':
                error = (_('Operator %(operator)s is not supported. Only'
                           ' equality operator is available for field'
                           ' %(field)s') %
                         {'operator': i.op, 'field': i.field})
                raise base.ClientSideError(error)
            evt_model_filter[i.field] = i.value
        else:
            trait_type = i.type or 'string'
            traits_filter.append({"key": i.field,
                                  trait_type: i._get_value_as_type(),
                                  "op": i.op})
    return storage.EventFilter(traits_filter=traits_filter,
                               admin_proj=admin_proj, **evt_model_filter)


class TraitsController(rest.RestController):
    """Works on Event Traits."""

    @v2_utils.requires_admin
    @wsme_pecan.wsexpose([Trait], wtypes.text, wtypes.text)
    def get_one(self, event_type, trait_name):
        """Return all instances of a trait for an event type.

        :param event_type: Event type to filter traits by
        :param trait_name: Trait to return values for
        """
        LOG.debug("Getting traits for %s", event_type)
        return [Trait._convert_storage_trait(t)
                for t in pecan.request.event_storage_conn
                .get_traits(event_type, trait_name)]

    @v2_utils.requires_admin
    @wsme_pecan.wsexpose([TraitDescription], wtypes.text)
    def get_all(self, event_type):
        """Return all trait names for an event type.

        :param event_type: Event type to filter traits by
        """
        get_trait_name = event_models.Trait.get_name_by_type
        return [TraitDescription(name=t['name'],
                                 type=get_trait_name(t['data_type']))
                for t in pecan.request.event_storage_conn
                .get_trait_types(event_type)]


class EventTypesController(rest.RestController):
    """Works on Event Types in the system."""

    traits = TraitsController()

    @v2_utils.requires_admin
    @wsme_pecan.wsexpose(None, wtypes.text)
    def get_one(self, event_type):
        """Unused API, will always return 404.

        :param event_type: A event type
        """
        pecan.abort(404)

    @v2_utils.requires_admin
    @wsme_pecan.wsexpose([six.text_type])
    def get_all(self):
        """Get all event types."""
        return list(pecan.request.event_storage_conn.get_event_types())


class EventsController(rest.RestController):
    """Works on Events."""

    @v2_utils.requires_context
    @wsme_pecan.wsexpose([Event], [EventQuery], int)
    def get_all(self, q=None, limit=None):
        """Return all events matching the query filters.

        :param q: Filter arguments for which Events to return
        :param limit: Maximum number of samples to be returned.
        """
        rbac.enforce("events:index", pecan.request)
        q = q or []
        limit = v2_utils.enforce_limit(limit)
        event_filter = _event_query_to_event_filter(q)
        return [Event(message_id=event.message_id,
                      event_type=event.event_type,
                      generated=event.generated,
                      traits=event.traits,
                      raw=event.raw)
                for event in
                pecan.request.event_storage_conn.get_events(event_filter,
                                                            limit)]

    @v2_utils.requires_context
    @wsme_pecan.wsexpose(Event, wtypes.text)
    def get_one(self, message_id):
        """Return a single event with the given message id.

        :param message_id: Message ID of the Event to be returned
        """
        rbac.enforce("events:show", pecan.request)
        filters = _build_rbac_query_filters()
        t_filter = filters['t_filter']
        admin_proj = filters['admin_proj']
        event_filter = storage.EventFilter(traits_filter=t_filter,
                                           admin_proj=admin_proj,
                                           message_id=message_id)
        events = [event for event
                  in pecan.request.event_storage_conn.get_events(event_filter)]
        if not events:
            raise base.EntityNotFound(_("Event"), message_id)

        if len(events) > 1:
            LOG.error(_("More than one event with "
                        "id %s returned from storage driver") % message_id)

        event = events[0]

        return Event(message_id=event.message_id,
                     event_type=event.event_type,
                     generated=event.generated,
                     traits=event.traits,
                     raw=event.raw)
