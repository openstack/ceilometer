#
# Copyright Ericsson AB 2013. All rights reserved
#
# Authors: Ildiko Vancsa <ildiko.vancsa@ericsson.com>
#          Balazs Gibizer <balazs.gibizer@ericsson.com>
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
"""Common functions for MongoDB and DB2 backends
"""
import pymongo

from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer.storage import base
from ceilometer.storage import models
from ceilometer.storage.mongo import utils as pymongo_utils
from ceilometer import utils

LOG = log.getLogger(__name__)


COMMON_AVAILABLE_CAPABILITIES = {
    'meters': {'query': {'simple': True,
                         'metadata': True}},
    'samples': {'query': {'simple': True,
                          'metadata': True,
                          'complex': True}},
    'events': {'query': {'simple': True}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


class Connection(base.Connection):
    """Base Connection class for MongoDB and DB2 drivers."""
    CAPABILITIES = utils.update_nested(base.Connection.CAPABILITIES,
                                       COMMON_AVAILABLE_CAPABILITIES)

    STORAGE_CAPABILITIES = utils.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )

    def get_meters(self, user=None, project=None, resource=None, source=None,
                   metaquery=None, pagination=None):
        """Return an iterable of models.Meter instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional resource filter.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param pagination: Optional pagination query.
        """

        if pagination:
            raise NotImplementedError('Pagination not implemented')

        metaquery = metaquery or {}

        q = {}
        if user is not None:
            q['user_id'] = user
        if project is not None:
            q['project_id'] = project
        if resource is not None:
            q['_id'] = resource
        if source is not None:
            q['source'] = source
        q.update(metaquery)

        for r in self.db.resource.find(q):
            for r_meter in r['meter']:
                yield models.Meter(
                    name=r_meter['counter_name'],
                    type=r_meter['counter_type'],
                    # Return empty string if 'counter_unit' is not valid for
                    # backward compatibility.
                    unit=r_meter.get('counter_unit', ''),
                    resource_id=r['_id'],
                    project_id=r['project_id'],
                    source=r['source'],
                    user_id=r['user_id'],
                )

    def get_samples(self, sample_filter, limit=None):
        """Return an iterable of model.Sample instances.

        :param sample_filter: Filter.
        :param limit: Maximum number of results to return.
        """
        if limit == 0:
            return []
        q = pymongo_utils.make_query_from_filter(sample_filter,
                                                 require_meter=False)

        return self._retrieve_samples(q,
                                      [("timestamp", pymongo.DESCENDING)],
                                      limit)

    def record_events(self, event_models):
        """Write the events to database.

        Return a list of events of type models.Event.DUPLICATE in case of
        trying to write an already existing event to the database, or
        models.Event.UNKONW_PROBLEM in case of any failures with recording the
        event in the database.

        :param event_models: a list of models.Event objects.
        """
        problem_events = []
        for event_model in event_models:
            traits = []
            if event_model.traits:
                for trait in event_model.traits:
                    traits.append({'trait_name': trait.name,
                                   'trait_type': trait.dtype,
                                   'trait_value': trait.value})
            try:
                self.db.event.insert(
                    {'_id': event_model.message_id,
                     'event_type': event_model.event_type,
                     'timestamp': event_model.generated,
                     'traits': traits})
            except pymongo.errors.DuplicateKeyError as ex:
                LOG.exception(_("Failed to record duplicated event: %s") % ex)
                problem_events.append((models.Event.DUPLICATE,
                                       event_model))
            except Exception as ex:
                LOG.exception(_("Failed to record event: %s") % ex)
                problem_events.append((models.Event.UNKNOWN_PROBLEM,
                                       event_model))
        return problem_events

    def get_events(self, event_filter):
        """Return an iter of models.Event objects.

        :param event_filter: storage.EventFilter object, consists of filters
                             for events that are stored in database.
        """
        q = pymongo_utils.make_events_query_from_filter(event_filter)
        for event in self.db.event.find(q):
            traits = []
            for trait in event['traits']:
                traits.append(models.Trait(name=trait['trait_name'],
                                           dtype=int(trait['trait_type']),
                                           value=trait['trait_value']))
            yield models.Event(message_id=event['_id'],
                               event_type=event['event_type'],
                               generated=event['timestamp'],
                               traits=traits)

    def get_event_types(self):
        """Return all event types as an iter of strings."""
        event_types = set()
        events = self.db.event.find()

        for event in events:
            event_type = event['event_type']
            if event_type not in event_types:
                event_types.add(event_type)
                yield event_type

    def get_trait_types(self, event_type):
        """Return a dictionary containing the name and data type of the trait.

        Only trait types for the provided event_type are returned.

        :param event_type: the type of the Event.
        """
        trait_names = set()
        events = self.db.event.find({'event_type': event_type})

        for event in events:
            for trait in event['traits']:
                trait_name = trait['trait_name']
                if trait_name not in trait_names:
                    # Here we check that our method return only unique
                    # trait types. Method will return only one trait type. It
                    # is proposed that certain trait name could have only one
                    # trait type.
                    trait_names.add(trait_name)
                    yield {'name': trait_name,
                           'data_type': trait['trait_type']}

    def get_traits(self, event_type, trait_name=None):
        """Return all trait instances associated with an event_type.

        If trait_type is specified, only return instances of that trait type.

        :param event_type: the type of the Event to filter by
        :param trait_name: the name of the Trait to filter by
        """
        if not trait_name:
            events = self.db.event.find({'event_type': event_type})
        else:
            # We choose events that simultaneously have event_type and certain
            # trait_name, and retrieve events contains only mentioned traits.
            events = self.db.event.find({'$and': [{'event_type': event_type},
                                        {'traits.trait_name': trait_name}]},
                                        {'traits': {'$elemMatch':
                                                    {'trait_name': trait_name}}
                                         })
        for event in events:
            for trait in event['traits']:
                yield models.Trait(name=trait['trait_name'],
                                   dtype=trait['trait_type'],
                                   value=trait['trait_value'])

    def query_samples(self, filter_expr=None, orderby=None, limit=None):
        if limit == 0:
            return []
        query_filter = {}
        orderby_filter = [("timestamp", pymongo.DESCENDING)]
        transformer = pymongo_utils.QueryTransformer()
        if orderby is not None:
            orderby_filter = transformer.transform_orderby(orderby)
        if filter_expr is not None:
            query_filter = transformer.transform_filter(filter_expr)

        return self._retrieve_samples(query_filter, orderby_filter, limit)

    def _retrieve_samples(self, query, orderby, limit):
        if limit is not None:
            samples = self.db.meter.find(query,
                                         limit=limit,
                                         sort=orderby)
        else:
            samples = self.db.meter.find(query,
                                         sort=orderby)

        for s in samples:
            # Remove the ObjectId generated by the database when
            # the sample was inserted. It is an implementation
            # detail that should not leak outside of the driver.
            del s['_id']
            # Backward compatibility for samples without units
            s['counter_unit'] = s.get('counter_unit', '')
            # Tolerate absence of recorded_at in older datapoints
            s['recorded_at'] = s.get('recorded_at')
            yield models.Sample(**s)
