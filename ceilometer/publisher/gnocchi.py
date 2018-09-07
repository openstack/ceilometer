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
import json
import operator
import pkg_resources
import threading
import uuid

from gnocchiclient import exceptions as gnocchi_exc
from keystoneauth1 import exceptions as ka_exceptions
from oslo_log import log
from oslo_utils import fnmatch
from oslo_utils import timeutils
import six
import six.moves.urllib.parse as urlparse
from stevedore import extension

from ceilometer import declarative
from ceilometer import gnocchi_client
from ceilometer.i18n import _
from ceilometer import keystone_client
from ceilometer import publisher

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
                        'metrics': (dict, list)}

    MANDATORY_EVENT_FIELDS = {'id': six.string_types}

    def __init__(self, definition_cfg, archive_policy_default,
                 archive_policy_override, plugin_manager):
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

        # NOTE(sileht): Convert old list to new dict format
        if isinstance(self.cfg['metrics'], list):
            values = [None] * len(self.cfg['metrics'])
            self.cfg['metrics'] = dict(zip(self.cfg['metrics'], values))

        for m, extra in self.cfg['metrics'].items():
            if not extra:
                extra = {}

            if not extra.get("archive_policy_name"):
                extra["archive_policy_name"] = archive_policy_default

            if archive_policy_override:
                extra["archive_policy_name"] = archive_policy_override

            # NOTE(sileht): For backward compat, this is after the override to
            # preserve the wierd previous behavior. We don't really care as we
            # deprecate it.
            if 'archive_policy' in self.cfg:
                LOG.warning("archive_policy '%s' for a resource-type (%s) is "
                            "deprecated, set it for each metric instead.",
                            self.cfg["archive_policy"],
                            self.cfg["resource_type"])
                extra["archive_policy_name"] = self.cfg['archive_policy']

            self.metrics[m] = extra

    @staticmethod
    def _check_required_and_types(expected, definition):
        for field, field_types in expected.items():
            if field not in definition:
                raise declarative.ResourceDefinitionException(
                    _("Required field %s not specified") % field, definition)
            if not isinstance(definition[field], field_types):
                raise declarative.ResourceDefinitionException(
                    _("Required field %(field)s should be a %(type)s") %
                    {'field': field, 'type': field_types}, definition)

    @staticmethod
    def _ensure_list(value):
        if isinstance(value, list):
            return value
        return [value]

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
        sample_dict = sample.as_dict()
        for name, definition in self._attributes.items():
            value = definition.parse(sample_dict)
            if value is not None:
                attrs[name] = value
        return attrs

    def event_attributes(self, event):
        attrs = {'type': self.cfg['resource_type']}
        traits = dict([(trait.name, trait.value) for trait in event.traits])
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


class GnocchiPublisher(publisher.ConfigPublisherBase):
    """Publisher class for recording metering data into the Gnocchi service.

    The publisher class records each meter into the gnocchi service
    configured in Ceilometer pipeline file. An example target may
    look like the following:

      gnocchi://?archive_policy=low&filter_project=gnocchi
    """
    def __init__(self, conf, parsed_url):
        super(GnocchiPublisher, self).__init__(conf, parsed_url)
        # TODO(jd) allow to override Gnocchi endpoint via the host in the URL
        options = urlparse.parse_qs(parsed_url.query)

        self.filter_project = options.get('filter_project', ['service'])[-1]

        resources_definition_file = options.get(
            'resources_definition_file', ['gnocchi_resources.yaml'])[-1]

        archive_policy_override = options.get('archive_policy', [None])[-1]
        self.resources_definition, self.archive_policies_definition = (
            self._load_definitions(conf, archive_policy_override,
                                   resources_definition_file))
        self.metric_map = dict((metric, rd) for rd in self.resources_definition
                               for metric in rd.metrics)

        timeout = options.get('timeout', [6.05])[-1]
        self._ks_client = keystone_client.get_client(conf)

        self.cache = None
        try:
            import oslo_cache
            oslo_cache.configure(conf)
            # NOTE(cdent): The default cache backend is a real but
            # noop backend. We don't want to use that here because
            # we want to avoid the cache pathways entirely if the
            # cache has not been configured explicitly.
            if conf.cache.enabled:
                cache_region = oslo_cache.create_region()
                self.cache = oslo_cache.configure_cache_region(
                    conf, cache_region)
                self.cache.key_mangler = cache_key_mangler
        except ImportError:
            pass
        except oslo_cache.exception.ConfigurationError as exc:
            LOG.warning('unable to configure oslo_cache: %s', exc)

        self._gnocchi_project_id = None
        self._gnocchi_project_id_lock = threading.Lock()
        self._gnocchi_resource_lock = LockedDefaultDict(threading.Lock)

        self._gnocchi = gnocchi_client.get_gnocchiclient(
            conf, request_timeout=timeout)
        self._already_logged_event_types = set()
        self._already_logged_metric_names = set()

        self._already_configured_archive_policies = False

    @staticmethod
    def _load_definitions(conf, archive_policy_override,
                          resources_definition_file):
        plugin_manager = extension.ExtensionManager(
            namespace='ceilometer.event.trait_plugin')
        data = declarative.load_definitions(
            conf, {}, resources_definition_file,
            pkg_resources.resource_filename(__name__,
                                            "data/gnocchi_resources.yaml"))

        archive_policy_default = data.get("archive_policy_default", "low")
        resource_defs = []
        for resource in data.get('resources', []):
            try:
                resource_defs.append(ResourcesDefinition(
                    resource,
                    archive_policy_default,
                    archive_policy_override,
                    plugin_manager))
            except Exception as exc:
                LOG.error("Failed to load resource due to error %s" %
                          exc)
        return resource_defs, data.get("archive_policies", [])

    def ensures_archives_policies(self):
        if not self._already_configured_archive_policies:
            for ap in self.archive_policies_definition:
                try:
                    self._gnocchi.archive_policy.get(ap["name"])
                except gnocchi_exc.ArchivePolicyNotFound:
                    self._gnocchi.archive_policy.create(ap)
            self._already_configured_archive_policies = True

    @property
    def gnocchi_project_id(self):
        if self._gnocchi_project_id is not None:
            return self._gnocchi_project_id
        with self._gnocchi_project_id_lock:
            if self._gnocchi_project_id is None:
                try:
                    project = self._ks_client.projects.find(
                        name=self.filter_project)
                except ka_exceptions.NotFound:
                    LOG.warning('filtered project not found in keystone,'
                                ' ignoring the filter_project '
                                'option')
                    self.filter_project = None
                    return None
                except Exception:
                    LOG.exception('fail to retrieve filtered project ')
                    raise
                self._gnocchi_project_id = project.id
                LOG.debug("filtered project found: %s",
                          self._gnocchi_project_id)
            return self._gnocchi_project_id

    def _is_swift_account_sample(self, sample):
        try:
            return (self.metric_map[sample.name].cfg['resource_type']
                    == 'swift_account')
        except KeyError:
            return False

    def _is_gnocchi_activity(self, sample):
        return (self.filter_project and self.gnocchi_project_id and (
            # avoid anything from the user used by gnocchi
            sample.project_id == self.gnocchi_project_id or
            # avoid anything in the swift account used by gnocchi
            (sample.resource_id == self.gnocchi_project_id and
             self._is_swift_account_sample(sample))
        ))

    def _get_resource_definition_from_event(self, event_type):
        for rd in self.resources_definition:
            operation = rd.event_match(event_type)
            if operation:
                return rd, operation

    def publish_samples(self, data):
        self.ensures_archives_policies()

        # NOTE(sileht): skip sample generated by gnocchi itself
        data = [s for s in data if not self._is_gnocchi_activity(s)]
        data.sort(key=operator.attrgetter('resource_id'))
        resource_grouped_samples = itertools.groupby(
            data, key=operator.attrgetter('resource_id'))

        gnocchi_data = {}
        measures = {}
        for resource_id, samples_of_resource in resource_grouped_samples:
            # NOTE(sileht): / is forbidden by Gnocchi
            resource_id = resource_id.replace('/', '_')

            for sample in samples_of_resource:
                metric_name = sample.name
                rd = self.metric_map.get(metric_name)
                if rd is None:
                    if metric_name not in self._already_logged_metric_names:
                        LOG.warning("metric %s is not handled by Gnocchi" %
                                    metric_name)
                        self._already_logged_metric_names.add(metric_name)
                    continue

                if resource_id not in gnocchi_data:
                    gnocchi_data[resource_id] = {
                        'resource_type': rd.cfg['resource_type'],
                        'resource': {"id": resource_id,
                                     "user_id": sample.user_id,
                                     "project_id": sample.project_id}}

                gnocchi_data[resource_id].setdefault(
                    "resource_extra", {}).update(rd.sample_attributes(sample))
                measures.setdefault(resource_id, {}).setdefault(
                    metric_name,
                    {"measures": [],
                     "archive_policy_name":
                     rd.metrics[metric_name]["archive_policy_name"],
                     "unit": sample.unit}
                )["measures"].append(
                    {'timestamp': sample.timestamp,
                     'value': sample.volume}
                )

        try:
            self.batch_measures(measures, gnocchi_data)
        except gnocchi_exc.ClientException as e:
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
                self._if_not_cached(resource_type, resource['id'],
                                    resource_extra)
            except gnocchi_exc.ClientException as e:
                LOG.error(six.text_type(e))
            except Exception as e:
                LOG.error(six.text_type(e), exc_info=True)

    @staticmethod
    def _extract_resources_from_error(e, resource_infos):
        resource_ids = set([r['original_resource_id']
                            for r in e.message['detail']])
        return [(resource_infos[rid]['resource_type'],
                 resource_infos[rid]['resource'],
                 resource_infos[rid]['resource_extra'])
                for rid in resource_ids]

    def batch_measures(self, measures, resource_infos):
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
            for resource_type, resource, resource_extra in resources:
                try:
                    resource.update(resource_extra)
                    self._create_resource(resource_type, resource)
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
                else:
                    if self.cache and resource_extra:
                        self.cache.set(resource['id'],
                                       self._hash_resource(resource_extra))

            # NOTE(sileht): we have created missing resources/metrics,
            # now retry to post measures
            self._gnocchi.metric.batch_resources_metrics_measures(
                measures, create_metrics=True)

        LOG.debug(
            "%d measures posted against %d metrics through %d resources",
            sum(len(m["measures"])
                for rid in measures
                for m in measures[rid].values()),
            sum(len(m) for m in measures.values()), len(resource_infos))

    def _create_resource(self, resource_type, resource):
        self._gnocchi.resource.create(resource_type, resource)
        LOG.debug('Resource %s created', resource["id"])

    def _update_resource(self, resource_type, res_id, resource_extra):
        self._gnocchi.resource.update(resource_type, res_id, resource_extra)
        LOG.debug('Resource %s updated', res_id)

    def _if_not_cached(self, resource_type, res_id, resource_extra):
        if self.cache:
            attribute_hash = self._hash_resource(resource_extra)
            if self._resource_cache_diff(res_id, attribute_hash):
                with self._gnocchi_resource_lock[res_id]:
                    # NOTE(luogangyi): there is a possibility that the
                    # resource was already built in cache by another
                    # ceilometer-notification-agent when we get the lock here.
                    if self._resource_cache_diff(res_id, attribute_hash):
                        self._update_resource(resource_type, res_id,
                                              resource_extra)
                        self.cache.set(res_id, attribute_hash)
                    else:
                        LOG.debug('Resource cache hit for %s', res_id)
                self._gnocchi_resource_lock.pop(res_id, None)
            else:
                LOG.debug('Resource cache hit for %s', res_id)
        else:
            self._update_resource(resource_type, res_id, resource_extra)

    @staticmethod
    def _hash_resource(resource):
        return hash(tuple(i for i in resource.items() if i[0] != 'metrics'))

    def _resource_cache_diff(self, key, attribute_hash):
        cached_hash = self.cache.get(key)
        return not cached_hash or cached_hash != attribute_hash

    def publish_events(self, events):
        for event in events:
            rd = self._get_resource_definition_from_event(event.event_type)
            if not rd:
                if event.event_type not in self._already_logged_event_types:
                    LOG.debug("No gnocchi definition for event type: %s",
                              event.event_type)
                    self._already_logged_event_types.add(event.event_type)
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
                resource_type, json.loads(query))
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
