#
# Copyright Ericsson AB 2013. All rights reserved
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
"""Common functions for MongoDB backend."""
import pymongo

from ceilometer.storage import base
from ceilometer.storage import models
from ceilometer.storage.mongo import utils as pymongo_utils
from ceilometer import utils


COMMON_AVAILABLE_CAPABILITIES = {
    'meters': {'query': {'simple': True,
                         'metadata': True}},
    'samples': {'query': {'simple': True,
                          'metadata': True,
                          'complex': True}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


class Connection(base.Connection):
    """Base Connection class for MongoDB driver."""
    CAPABILITIES = utils.update_nested(base.Connection.CAPABILITIES,
                                       COMMON_AVAILABLE_CAPABILITIES)

    STORAGE_CAPABILITIES = utils.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )

    def get_meters(self, user=None, project=None, resource=None, source=None,
                   metaquery=None, limit=None, unique=False):
        """Return an iterable of models.Meter instances

        :param user: Optional ID for user that owns the resource.
        :param project: Optional ID for project that owns the resource.
        :param resource: Optional resource filter.
        :param source: Optional source filter.
        :param metaquery: Optional dict with metadata to match on.
        :param limit: Maximum number of results to return.
        :param unique: If set to true, return only unique meter information.
        """
        if limit == 0:
            return

        metaquery = pymongo_utils.improve_keys(metaquery, metaquery=True) or {}

        q = {}
        if user == 'None':
            q['user_id'] = None
        elif user is not None:
            q['user_id'] = user
        if project == 'None':
            q['project_id'] = None
        elif project is not None:
            q['project_id'] = project
        if resource == 'None':
            q['_id'] = None
        elif resource is not None:
            q['_id'] = resource
        if source is not None:
            q['source'] = source
        q.update(metaquery)

        count = 0
        if unique:
            meter_names = set()

        for r in self.db.resource.find(q):
            for r_meter in r['meter']:
                if unique:
                    if r_meter['counter_name'] in meter_names:
                        continue
                    else:
                        meter_names.add(r_meter['counter_name'])

                if limit and count >= limit:
                    return
                else:
                    count += 1

                if unique:
                    yield models.Meter(
                        name=r_meter['counter_name'],
                        type=r_meter['counter_type'],
                        # Return empty string if 'counter_unit' is not valid
                        # for backward compatibility.
                        unit=r_meter.get('counter_unit', ''),
                        resource_id=None,
                        project_id=None,
                        source=None,
                        user_id=None)
                else:
                    yield models.Meter(
                        name=r_meter['counter_name'],
                        type=r_meter['counter_type'],
                        # Return empty string if 'counter_unit' is not valid
                        # for backward compatibility.
                        unit=r_meter.get('counter_unit', ''),
                        resource_id=r['_id'],
                        project_id=r['project_id'],
                        source=r['source'],
                        user_id=r['user_id'])

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
            # Compatibility with MongoDB 3.+
            s['counter_volume'] = float(s.get('counter_volume'))
            # Tolerate absence of recorded_at in older datapoints
            s['recorded_at'] = s.get('recorded_at')
            # Check samples for metadata and "unquote" key if initially it
            # was started with '$'.
            if s.get('resource_metadata'):
                s['resource_metadata'] = pymongo_utils.unquote_keys(
                    s.get('resource_metadata'))
            yield models.Sample(**s)
