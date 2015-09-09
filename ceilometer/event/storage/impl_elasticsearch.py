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
import operator

import elasticsearch as es
from elasticsearch import helpers
from oslo_log import log
from oslo_utils import netutils
from oslo_utils import timeutils
import six

from ceilometer.event.storage import base
from ceilometer.event.storage import models
from ceilometer.i18n import _LE, _LI
from ceilometer import storage
from ceilometer import utils

LOG = log.getLogger(__name__)


AVAILABLE_CAPABILITIES = {
    'events': {'query': {'simple': True}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


class Connection(base.Connection):
    """Put the event data into an ElasticSearch db.

    Events in ElasticSearch are indexed by day and stored by event_type.
    An example document::

      {"_index":"events_2014-10-21",
       "_type":"event_type0",
       "_id":"dc90e464-65ab-4a5d-bf66-ecb956b5d779",
       "_score":1.0,
       "_source":{"timestamp": "2014-10-21T20:02:09.274797"
                  "traits": {"id4_0": "2014-10-21T20:02:09.274797",
                             "id3_0": 0.7510790937279408,
                             "id2_0": 5,
                             "id1_0": "18c97ba1-3b74-441a-b948-a702a30cbce2"}
                 }
      }
    """

    CAPABILITIES = utils.update_nested(base.Connection.CAPABILITIES,
                                       AVAILABLE_CAPABILITIES)
    STORAGE_CAPABILITIES = utils.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )
    index_name = 'events'
    # NOTE(gordc): mainly for testing, data is not searchable after write,
    #              it is only searchable after periodic refreshes.
    _refresh_on_write = False

    def __init__(self, url):
        url_split = netutils.urlsplit(url)
        self.conn = es.Elasticsearch(url_split.netloc)

    def upgrade(self):
        iclient = es.client.IndicesClient(self.conn)
        ts_template = {
            'template': '*',
            'mappings': {'_default_':
                         {'_timestamp': {'enabled': True,
                                         'store': True},
                          'properties': {'traits': {'type': 'nested'}}}}}
        iclient.put_template(name='enable_timestamp', body=ts_template)

    def record_events(self, events):

        def _build_bulk_index(event_list):
            for ev in event_list:
                traits = {t.name: t.value for t in ev.traits}
                yield {'_op_type': 'create',
                       '_index': '%s_%s' % (self.index_name,
                                            ev.generated.date().isoformat()),
                       '_type': ev.event_type,
                       '_id': ev.message_id,
                       '_source': {'timestamp': ev.generated.isoformat(),
                                   'traits': traits,
                                   'raw': ev.raw}}

        error = None
        for ok, result in helpers.streaming_bulk(
                self.conn, _build_bulk_index(events)):
            if not ok:
                __, result = result.popitem()
                if result['status'] == 409:
                    LOG.info(_LI('Duplicate event detected, skipping it: %s')
                             % result)
                else:
                    LOG.exception(_LE('Failed to record event: %s') % result)
                    error = storage.StorageUnknownWriteError(result)

        if self._refresh_on_write:
            self.conn.indices.refresh(index='%s_*' % self.index_name)
            while self.conn.cluster.pending_tasks(local=True)['tasks']:
                pass
        if error:
            raise error

    def _make_dsl_from_filter(self, indices, ev_filter):
        q_args = {}
        filters = []

        if ev_filter.start_timestamp:
            filters.append({'range': {'timestamp':
                           {'ge': ev_filter.start_timestamp.isoformat()}}})
            while indices[0] < (
                '%s_%s' % (self.index_name,
                           ev_filter.start_timestamp.date().isoformat())):
                del indices[0]
        if ev_filter.end_timestamp:
            filters.append({'range': {'timestamp':
                           {'le': ev_filter.end_timestamp.isoformat()}}})
            while indices[-1] > (
                '%s_%s' % (self.index_name,
                           ev_filter.end_timestamp.date().isoformat())):
                del indices[-1]
        q_args['index'] = indices

        if ev_filter.event_type:
            q_args['doc_type'] = ev_filter.event_type
        if ev_filter.message_id:
            filters.append({'term': {'_id': ev_filter.message_id}})
        if ev_filter.traits_filter or ev_filter.admin_proj:
            trait_filters = []
            or_cond = []
            for t_filter in ev_filter.traits_filter or []:
                value = None
                for val_type in ['integer', 'string', 'float', 'datetime']:
                    if t_filter.get(val_type):
                        value = t_filter.get(val_type)
                        if isinstance(value, six.string_types):
                            value = value.lower()
                        elif isinstance(value, datetime.datetime):
                            value = value.isoformat()
                        break
                if t_filter.get('op') in ['gt', 'ge', 'lt', 'le']:
                    op = (t_filter.get('op').replace('ge', 'gte')
                          .replace('le', 'lte'))
                    trait_filters.append(
                        {'range': {t_filter['key']: {op: value}}})
                else:
                    tf = {"query": {"query_string": {
                        "query": "%s: \"%s\"" % (t_filter['key'], value)}}}
                    if t_filter.get('op') == 'ne':
                        tf = {"not": tf}
                    trait_filters.append(tf)
            if ev_filter.admin_proj:
                or_cond = [{'missing': {'field': 'project_id'}},
                           {'term': {'project_id': ev_filter.admin_proj}}]
            filters.append(
                {'nested': {'path': 'traits', 'query': {'filtered': {
                    'filter': {'bool': {'must': trait_filters,
                                        'should': or_cond}}}}}})

        q_args['body'] = {'query': {'filtered':
                                    {'filter': {'bool': {'must': filters}}}}}
        return q_args

    def get_events(self, event_filter, limit=None):
        if limit == 0:
            return
        iclient = es.client.IndicesClient(self.conn)
        indices = iclient.get_mapping('%s_*' % self.index_name).keys()
        if indices:
            filter_args = self._make_dsl_from_filter(indices, event_filter)
            if limit is not None:
                filter_args['size'] = limit
            results = self.conn.search(fields=['_id', 'timestamp',
                                               '_type', '_source'],
                                       sort='timestamp:asc',
                                       **filter_args)
            trait_mappings = {}
            for record in results['hits']['hits']:
                trait_list = []
                if not record['_type'] in trait_mappings:
                    trait_mappings[record['_type']] = list(
                        self.get_trait_types(record['_type']))
                for key in record['_source']['traits'].keys():
                    value = record['_source']['traits'][key]
                    for t_map in trait_mappings[record['_type']]:
                        if t_map['name'] == key:
                            dtype = t_map['data_type']
                            break
                    else:
                        dtype = models.Trait.TEXT_TYPE
                    trait_list.append(models.Trait(
                        name=key, dtype=dtype,
                        value=models.Trait.convert_value(dtype, value)))
                gen_ts = timeutils.normalize_time(timeutils.parse_isotime(
                    record['_source']['timestamp']))
                yield models.Event(message_id=record['_id'],
                                   event_type=record['_type'],
                                   generated=gen_ts,
                                   traits=sorted(
                                       trait_list,
                                       key=operator.attrgetter('dtype')),
                                   raw=record['_source']['raw'])

    def get_event_types(self):
        iclient = es.client.IndicesClient(self.conn)
        es_mappings = iclient.get_mapping('%s_*' % self.index_name)
        seen_types = set()
        for index in es_mappings.keys():
            for ev_type in es_mappings[index]['mappings'].keys():
                seen_types.add(ev_type)
        # TODO(gordc): tests assume sorted ordering but backends are not
        #              explicitly ordered.
        # NOTE: _default_ is a type that appears in all mappings but is not
        #       real 'type'
        seen_types.discard('_default_')
        return sorted(list(seen_types))

    @staticmethod
    def _remap_es_types(d_type):
        if d_type == 'string':
            d_type = 'text'
        elif d_type == 'long':
            d_type = 'int'
        elif d_type == 'double':
            d_type = 'float'
        elif d_type == 'date' or d_type == 'date_time':
            d_type = 'datetime'
        return d_type

    def get_trait_types(self, event_type):
        iclient = es.client.IndicesClient(self.conn)
        es_mappings = iclient.get_mapping('%s_*' % self.index_name)
        seen_types = []
        for index in es_mappings.keys():
            # if event_type exists in index and has traits
            if (es_mappings[index]['mappings'].get(event_type) and
                    es_mappings[index]['mappings'][event_type]['properties']
                    ['traits'].get('properties')):
                for t_type in (es_mappings[index]['mappings'][event_type]
                               ['properties']['traits']['properties'].keys()):
                    d_type = (es_mappings[index]['mappings'][event_type]
                              ['properties']['traits']['properties']
                              [t_type]['type'])
                    d_type = models.Trait.get_type_by_name(
                        self._remap_es_types(d_type))
                    if (t_type, d_type) not in seen_types:
                        yield {'name': t_type, 'data_type': d_type}
                        seen_types.append((t_type, d_type))

    def get_traits(self, event_type, trait_type=None):
        t_types = dict((res['name'], res['data_type'])
                       for res in self.get_trait_types(event_type))
        if not t_types or (trait_type and trait_type not in t_types.keys()):
            return
        result = self.conn.search('%s_*' % self.index_name, event_type)
        for ev in result['hits']['hits']:
            if trait_type and ev['_source']['traits'].get(trait_type):
                yield models.Trait(
                    name=trait_type,
                    dtype=t_types[trait_type],
                    value=models.Trait.convert_value(
                        t_types[trait_type],
                        ev['_source']['traits'][trait_type]))
            else:
                for trait in ev['_source']['traits'].keys():
                    yield models.Trait(
                        name=trait,
                        dtype=t_types[trait],
                        value=models.Trait.convert_value(
                            t_types[trait],
                            ev['_source']['traits'][trait]))
