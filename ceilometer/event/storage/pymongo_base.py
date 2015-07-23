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
from oslo_log import log
import pymongo

from ceilometer.event.storage import base
from ceilometer.event.storage import models
from ceilometer.i18n import _LE, _LI
from ceilometer.storage.mongo import utils as pymongo_utils
from ceilometer import utils

LOG = log.getLogger(__name__)


COMMON_AVAILABLE_CAPABILITIES = {
    'events': {'query': {'simple': True}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


class Connection(base.Connection):
    """Base event Connection class for MongoDB and DB2 drivers."""
    CAPABILITIES = utils.update_nested(base.Connection.CAPABILITIES,
                                       COMMON_AVAILABLE_CAPABILITIES)

    STORAGE_CAPABILITIES = utils.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )

    def record_events(self, event_models):
        """Write the events to database.

        :param event_models: a list of models.Event objects.
        """
        error = None
        for event_model in event_models:
            traits = []
            if event_model.traits:
                for trait in event_model.traits:
                    traits.append({'trait_name': trait.name,
                                   'trait_type': trait.dtype,
                                   'trait_value': trait.value})
            try:
                self.db.event.insert_one(
                    {'_id': event_model.message_id,
                     'event_type': event_model.event_type,
                     'timestamp': event_model.generated,
                     'traits': traits, 'raw': event_model.raw})
            except pymongo.errors.DuplicateKeyError as ex:
                LOG.info(_LI("Duplicate event detected, skipping it: %s") % ex)
            except Exception as ex:
                LOG.exception(_LE("Failed to record event: %s") % ex)
                error = ex
        if error:
            raise error

    def get_events(self, event_filter, limit=None):
        """Return an iter of models.Event objects.

        :param event_filter: storage.EventFilter object, consists of filters
                             for events that are stored in database.
        :param limit: Maximum number of results to return.
        """
        if limit == 0:
            return
        q = pymongo_utils.make_events_query_from_filter(event_filter)
        if limit is not None:
            results = self.db.event.find(q, limit=limit)
        else:
            results = self.db.event.find(q)
        for event in results:
            traits = []
            for trait in event['traits']:
                traits.append(models.Trait(name=trait['trait_name'],
                                           dtype=int(trait['trait_type']),
                                           value=trait['trait_value']))
            yield models.Event(message_id=event['_id'],
                               event_type=event['event_type'],
                               generated=event['timestamp'],
                               traits=traits, raw=event.get('raw'))

    def get_event_types(self):
        """Return all event types as an iter of strings."""
        return self.db.event.distinct('event_type')

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
