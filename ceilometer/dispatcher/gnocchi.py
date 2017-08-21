#
# Copyright 2014-2015 eNovance
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
from collections import defaultdict
import hashlib
import itertools
import operator
import pkg_resources
import threading
import uuid

from gnocchiclient import exceptions as gnocchi_exc
from keystoneauth1 import exceptions as ka_exceptions
from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import fnmatch
from oslo_utils import timeutils
import six
from stevedore import extension

from ceilometer import declarative
from ceilometer import dispatcher
from ceilometer import gnocchi_client
from ceilometer.i18n import _
from ceilometer import keystone_client

NAME_ENCODED = __name__.encode('utf-8')
CACHE_NAMESPACE = uuid.UUID(bytes=hashlib.md5(NAME_ENCODED).digest())
LOG = log.getLogger(__name__)


def cache_key_mangler(key):
    """Construct an opaque cache key."""
    if six.PY2:
        key = key.encode('utf-8')
    return uuid.uuid5(CACHE_NAMESPACE, key).hex


EVENT_CREATE, EVENT_UPDATE, EVENT_DELETE = ("create", "update", "delete")


class ResourcesDefinition(object):

    MANDATORY_FIELDS = {'resource_type': six.string_types,
                        'metrics': list}

    MANDATORY_EVENT_FIELDS = {'id': six.string_types}

    def __init__(self, definition_cfg, default_archive_policy, plugin_manager):
        self._default_archive_policy = default_archive_policy
        self.cfg = definition_cfg

        self._check_required_and_types(self.MANDATORY_FIELDS, self.cfg)

        if self.support_events():
            self._check_required_and_types(self.MANDATORY_EVENT_FIELDS,
                                           self.cfg['event_attributes'])

        self._attributes = {}
        for name, attr_cfg in self.cfg.get('attributes', {}).items():
            self._attributes[name] = declarative.Definition(name, attr_cfg,
                                                            plugin_manager)

        self._event_attributes = {}
        for name, attr_cfg in self.cfg.get('event_attributes', {}).items():
            self._event_attributes[name] = declarative.Definition(
                name, attr_cfg, plugin_manager)

        self.metrics = {}
        for t in self.cfg['metrics']:
            archive_policy = self.cfg.get('archive_policy',
                                          self._default_archive_policy)
            if archive_policy is None:
                self.metrics[t] = {}
            else:
                self.metrics[t] = dict(archive_policy_name=archive_policy)

    @staticmethod
    def _check_required_and_types(expected, definition):
        for field, field_type in expected.items():
            if field not in definition:
                raise declarative.ResourceDefinitionException(
                    _("Required field %s not specified") % field, definition)
            if not isinstance(definition[field], field_type):
                raise declarative.ResourceDefinitionException(
                    _("Required field %(field)s should be a %(type)s") %
                    {'field': field, 'type': field_type}, definition)

    @staticmethod
    def _ensure_list(value):
        if isinstance(value, list):
            return value
        return [value]

    def metric_match(self, metric_name):
        for t in self.cfg['metrics']:
            if fnmatch.fnmatch(metric_name, t):
                return True
        return False

    def support_events(self):
        for e in ["event_create", "event_delete", "event_update"]:
            if e in self.cfg:
                return True
        return False

    def event_match(self, event_type):
        for e in self._ensure_list(self.cfg.get('event_create', [])):
            if fnmatch.fnmatch(event_type, e):
                return EVENT_CREATE
        for e in self._ensure_list(self.cfg.get('event_delete', [])):
            if fnmatch.fnmatch(event_type, e):
                return EVENT_DELETE
        for e in self._ensure_list(self.cfg.get('event_update', [])):
            if fnmatch.fnmatch(event_type, e):
                return EVENT_UPDATE

    def sample_attributes(self, sample):
        attrs = {}
        for name, definition in self._attributes.items():
            value = definition.parse(sample)
            if value is not None:
                attrs[name] = value
        return attrs

    def event_attributes(self, event):
        attrs = {'type': self.cfg['resource_type']}
        traits = dict([(trait[0], trait[2]) for trait in event['traits']])
        for attr, field in self.cfg.get('event_attributes', {}).items():
            value = traits.get(field)
            if value is not None:
                attrs[attr] = value
        return attrs


class LockedDefaultDict(defaultdict):
    """defaultdict with lock to handle threading

    Dictionary only deletes if nothing is accessing dict and nothing is holding
    lock to be deleted. If both cases are not true, it will skip delete.
    """
    def __init__(self, *args, **kwargs):
        self.lock = threading.Lock()
        super(LockedDefaultDict, self).__init__(*args, **kwargs)

    def __getitem__(self, key):
        with self.lock:
            return super(LockedDefaultDict, self).__getitem__(key)

    def pop(self, key, *args):
        with self.lock:
            key_lock = super(LockedDefaultDict, self).__getitem__(key)
            if key_lock.acquire(False):
                try:
                    super(LockedDefaultDict, self).pop(key, *args)
                finally:
                    key_lock.release()


class GnocchiDispatcher(dispatcher.MeterDispatcherBase,
                        dispatcher.EventDispatcherBase):
    """Dispatcher class for recording metering data into the Gnocchi service.

    The dispatcher class records each meter into the gnocchi service
    configured in ceilometer configuration file. An example configuration may
    look like the following:

    [dispatcher_gnocchi]
    archive_policy = low

    To enable this dispatcher, the following section needs to be present in
    ceilometer.conf file

    [DEFAULT]
    meter_dispatchers = gnocchi
    event_dispatchers = gnocchi
    """
    def __init__(self, conf):
        super(GnocchiDispatcher, self).__init__(conf)
        self.conf = conf
        self.filter_service_activity = (
            conf.dispatcher_gnocchi.filter_service_activity)
        self._ks_client = keystone_client.get_client(conf)
        self.resources_definition = self._load_resources_definitions(conf)

        self.cache = None
        try:
            import oslo_cache
            oslo_cache.configure(self.conf)
            # NOTE(cdent): The default cache backend is a real but
            # noop backend. We don't want to use that here because
            # we want to avoid the cache pathways entirely if the
            # cache has not been configured explicitly.
            if self.conf.cache.enabled:
                cache_region = oslo_cache.create_region()
                self.cache = oslo_cache.configure_cache_region(
                    self.conf, cache_region)
                self.cache.key_mangler = cache_key_mangler
        except ImportError:
            pass
        except oslo_cache.exception.ConfigurationError as exc:
            LOG.warning('unable to configure oslo_cache: %s', exc)

        self._gnocchi_project_id = None
        self._gnocchi_project_id_lock = threading.Lock()
        self._gnocchi_resource_lock = LockedDefaultDict(threading.Lock)

        self._gnocchi = gnocchi_client.get_gnocchiclient(conf)
        self._already_logged_event_types = set()
        self._already_logged_metric_names = set()

    @classmethod
    def _load_resources_definitions(cls, conf):
        plugin_manager = extension.ExtensionManager(
            namespace='ceilometer.event.trait_plugin')
        data = declarative.load_definitions(
            conf, {}, conf.dispatcher_gnocchi.resources_definition_file,
            pkg_resources.resource_filename(__name__,
                                            "data/gnocchi_resources.yaml"))
        resource_defs = []
        for resource in data.get('resources', []):
            try:
                resource_defs.append(ResourcesDefinition(
                    resource,
                    conf.dispatcher_gnocchi.archive_policy, plugin_manager))
            except Exception as exc:
                LOG.error("Failed to load resource due to error %s" %
                          exc)
        return resource_defs

    @property
    def gnocchi_project_id(self):
        if self._gnocchi_project_id is not None:
            return self._gnocchi_project_id
        with self._gnocchi_project_id_lock:
            if self._gnocchi_project_id is None:
                try:
                    project = self._ks_client.projects.find(
                        name=self.conf.dispatcher_gnocchi.filter_project)
                except ka_exceptions.NotFound:
                    LOG.warning('gnocchi project not found in keystone,'
                                ' ignoring the filter_service_activity '
                                'option')
                    self.filter_service_activity = False
                    return None
                except Exception:
                    LOG.exception('fail to retrieve user of Gnocchi '
                                  'service')
                    raise
                self._gnocchi_project_id = project.id
                LOG.debug("gnocchi project found: %s", self.gnocchi_project_id)
            return self._gnocchi_project_id

    def _is_swift_account_sample(self, sample):
        return bool([rd for rd in self.resources_definition
                     if rd.cfg['resource_type'] == 'swift_account'
                     and rd.metric_match(sample['counter_name'])])

    def _is_gnocchi_activity(self, sample):
        return (self.filter_service_activity and self.gnocchi_project_id and (
            # avoid anything from the user used by gnocchi
            sample['project_id'] == self.gnocchi_project_id or
            # avoid anything in the swift account used by gnocchi
            (sample['resource_id'] == self.gnocchi_project_id and
             self._is_swift_account_sample(sample))
        ))

    def _get_resource_definition_from_metric(self, metric_name):
        for rd in self.resources_definition:
            if rd.metric_match(metric_name):
                return rd

    def _get_resource_definition_from_event(self, event_type):
        for rd in self.resources_definition:
            operation = rd.event_match(event_type)
            if operation:
                return rd, operation

    def record_metering_data(self, data):
        # We may have receive only one counter on the wire
        if not isinstance(data, list):
            data = [data]
        # NOTE(sileht): skip sample generated by gnocchi itself
        data = [s for s in data if not self._is_gnocchi_activity(s)]

        data.sort(key=lambda s: (s['resource_id'], s['counter_name']))
        resource_grouped_samples = itertools.groupby(
            data, key=operator.itemgetter('resource_id'))

        gnocchi_data = {}
        measures = {}
        stats = dict(measures=0, resources=0, metrics=0)
        for resource_id, samples_of_resource in resource_grouped_samples:
            # NOTE(sileht): / is forbidden by Gnocchi
            resource_id = resource_id.replace('/', '_')

            stats['resources'] += 1
            metric_grouped_samples = itertools.groupby(
                list(samples_of_resource),
                key=operator.itemgetter('counter_name'))

            res_info = {}
            for metric_name, samples in metric_grouped_samples:
                stats['metrics'] += 1

                samples = list(samples)
                rd = self._get_resource_definition_from_metric(metric_name)
                if rd is None:
                    if metric_name not in self._already_logged_metric_names:
                        LOG.warning("metric %s is not handled by Gnocchi" %
                                    metric_name)
                        self._already_logged_metric_names.add(metric_name)
                    continue
                if rd.cfg.get("ignore"):
                    continue

                res_info['resource_type'] = rd.cfg['resource_type']
                res_info.setdefault("resource", {}).update({
                    "id": resource_id,
                    "user_id": samples[0]['user_id'],
                    "project_id": samples[0]['project_id'],
                    "metrics": rd.metrics,
                })

                for sample in samples:
                    res_info.setdefault("resource_extra", {}).update(
                        rd.sample_attributes(sample))
                    m = measures.setdefault(resource_id, {}).setdefault(
                        metric_name, [])
                    m.append({'timestamp': sample['timestamp'],
                              'value': sample['counter_volume']})
                    unit = sample['counter_unit']
                    metric = sample['counter_name']
                    res_info['resource']['metrics'][metric]['unit'] = unit

                stats['measures'] += len(measures[resource_id][metric_name])
                res_info["resource"].update(res_info["resource_extra"])
                if res_info:
                    gnocchi_data[resource_id] = res_info

        try:
            self.batch_measures(measures, gnocchi_data, stats)
        except (gnocchi_exc.ClientException,
                ka_exceptions.ConnectFailure) as e:
            LOG.error(six.text_type(e))
        except Exception as e:
            LOG.error(six.text_type(e), exc_info=True)

        for info in gnocchi_data.values():
            resource = info["resource"]
            resource_type = info["resource_type"]
            resource_extra = info["resource_extra"]
            if not resource_extra:
                continue
            try:
                self._if_not_cached("update", resource_type, resource,
                                    self._update_resource, resource_extra)
            except gnocchi_exc.ClientException as e:
                LOG.error(six.text_type(e))
            except Exception as e:
                LOG.error(six.text_type(e), exc_info=True)

    @staticmethod
    def _extract_resources_from_error(e, resource_infos):
        resource_ids = set([r['original_resource_id']
                            for r in e.message['detail']])
        return [(resource_infos[rid]['resource_type'],
                 resource_infos[rid]['resource'])
                for rid in resource_ids]

    def batch_measures(self, measures, resource_infos, stats):
        # NOTE(sileht): We don't care about error here, we want
        # resources metadata always been updated
        try:
            self._gnocchi.metric.batch_resources_metrics_measures(
                measures, create_metrics=True)
        except gnocchi_exc.BadRequest as e:
            if not isinstance(e.message, dict):
                raise
            if e.message.get('cause') != 'Unknown resources':
                raise

            resources = self._extract_resources_from_error(e, resource_infos)
            for resource_type, resource in resources:
                try:
                    self._if_not_cached("create", resource_type, resource,
                                        self._create_resource)
                except gnocchi_exc.ResourceAlreadyExists:
                    # NOTE(sileht): resource created in the meantime
                    pass
                except gnocchi_exc.ClientException as e:
                    LOG.error('Error creating resource %(id)s: %(err)s',
                              {'id': resource['id'], 'err': six.text_type(e)})
                    # We cannot post measures for this resource
                    # and we can't patch it later
                    del measures[resource['id']]
                    del resource_infos[resource['id']]

            # NOTE(sileht): we have created missing resources/metrics,
            # now retry to post measures
            self._gnocchi.metric.batch_resources_metrics_measures(
                measures, create_metrics=True)

        # FIXME(sileht): take care of measures removed in stats
        LOG.debug("%(measures)d measures posted against %(metrics)d "
                  "metrics through %(resources)d resources", stats)

    def _create_resource(self, resource_type, resource):
        self._gnocchi.resource.create(resource_type, resource)
        LOG.debug('Resource %s created', resource["id"])

    def _update_resource(self, resource_type, resource, resource_extra):
        self._gnocchi.resource.update(resource_type,
                                      resource["id"],
                                      resource_extra)
        LOG.debug('Resource %s updated', resource["id"])

    def _if_not_cached(self, operation, resource_type, resource, method,
                       *args, **kwargs):
        if self.cache:
            cache_key = resource['id']
            attribute_hash = self._check_resource_cache(cache_key, resource)
            hit = False
            if attribute_hash:
                with self._gnocchi_resource_lock[cache_key]:
                    # NOTE(luogangyi): there is a possibility that the
                    # resource was already built in cache by another
                    # ceilometer-collector when we get the lock here.
                    attribute_hash = self._check_resource_cache(cache_key,
                                                                resource)
                    if attribute_hash:
                        method(resource_type, resource, *args, **kwargs)
                        self.cache.set(cache_key, attribute_hash)
                    else:
                        hit = True
                        LOG.debug('resource cache recheck hit for '
                                  '%s %s', operation, cache_key)
                self._gnocchi_resource_lock.pop(cache_key, None)
            else:
                hit = True
                LOG.debug('Resource cache hit for %s %s', operation, cache_key)
            if hit and operation == "create":
                raise gnocchi_exc.ResourceAlreadyExists()
        else:
            method(resource_type, resource, *args, **kwargs)

    def _check_resource_cache(self, key, resource_data):
        cached_hash = self.cache.get(key)
        attribute_hash = hash(frozenset(filter(lambda x: x[0] != "metrics",
                                               resource_data.items())))
        if not cached_hash or cached_hash != attribute_hash:
            return attribute_hash
        else:
            return None

    def record_events(self, events):
        for event in events:
            rd = self._get_resource_definition_from_event(event['event_type'])
            if not rd:
                if event['event_type'] not in self._already_logged_event_types:
                    LOG.debug("No gnocchi definition for event type: %s",
                              event['event_type'])
                    self._already_logged_event_types.add(event['event_type'])
                continue

            rd, operation = rd
            if operation == EVENT_DELETE:
                self._delete_event(rd, event)

    def _delete_event(self, rd, event):
        ended_at = timeutils.utcnow().isoformat()

        resource = rd.event_attributes(event)
        associated_resources = rd.cfg.get('event_associated_resources', {})

        if associated_resources:
            to_end = itertools.chain([resource], *[
                self._search_resource(resource_type, query % resource['id'])
                for resource_type, query in associated_resources.items()
            ])
        else:
            to_end = [resource]

        for resource in to_end:
            self._set_ended_at(resource, ended_at)

    def _search_resource(self, resource_type, query):
        try:
            return self._gnocchi.resource.search(
                resource_type, jsonutils.loads(query))
        except Exception:
            LOG.error("Fail to search resource type %{resource_type}s "
                      "with '%{query}s'",
                      {'resource_type': resource_type, 'query': query},
                      exc_info=True)
        return []

    def _set_ended_at(self, resource, ended_at):
        try:
            self._gnocchi.resource.update(resource['type'], resource['id'],
                                          {'ended_at': ended_at})
        except gnocchi_exc.ResourceNotFound:
            LOG.debug("Delete event received on unexisting resource (%s), "
                      "ignore it.", resource['id'])
        except Exception:
            LOG.error("Fail to update the resource %s", resource,
                      exc_info=True)
        LOG.debug('Resource %s ended at %s' % (resource["id"], ended_at))
