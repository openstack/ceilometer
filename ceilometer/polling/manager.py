#
# Copyright 2013 Julien Danjou
# Copyright 2014-2017 Red Hat, Inc
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

import collections
import itertools
import logging
import random
import uuid

from concurrent import futures
import cotyledon
from futurist import periodics
from keystoneauth1 import exceptions as ka_exceptions
from oslo_config import cfg
from oslo_log import log
import oslo_messaging
from oslo_utils import timeutils
import six
from six.moves.urllib import parse as urlparse
from stevedore import extension
from tooz import coordination

from ceilometer import agent
from ceilometer import keystone_client
from ceilometer import messaging
from ceilometer.polling import plugin_base
from ceilometer.publisher import utils as publisher_utils
from ceilometer import utils

LOG = log.getLogger(__name__)

OPTS = [
    cfg.BoolOpt('batch_polled_samples',
                default=True,
                deprecated_for_removal=True,
                help='To reduce polling agent load, samples are sent to the '
                     'notification agent in a batch. To gain higher '
                     'throughput at the cost of load set this to False. '
                     'This option is deprecated, to disable batching set '
                     'batch_size = 0 in the polling group.'
                ),
]

POLLING_OPTS = [
    cfg.StrOpt('cfg_file',
               default="polling.yaml",
               help="Configuration file for polling definition."
               ),
    cfg.StrOpt('partitioning_group_prefix',
               deprecated_group='central',
               help='Work-load partitioning group prefix. Use only if you '
                    'want to run multiple polling agents with different '
                    'config files. For each sub-group of the agent '
                    'pool with the same partitioning_group_prefix a disjoint '
                    'subset of pollsters should be loaded.'),
    cfg.IntOpt('batch_size',
               default=50,
               help='Batch size of samples to send to notification agent, '
                    'Set to 0 to disable'),
]


def hash_of_set(s):
    return str(hash(frozenset(s)))


class PollingException(agent.ConfigException):
    def __init__(self, message, cfg):
        super(PollingException, self).__init__('Polling', message, cfg)


class Resources(object):
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        self._resources = []
        self._discovery = []
        self.blacklist = []

    def setup(self, source):
        self._resources = source.resources
        self._discovery = source.discovery

    def get(self, discovery_cache=None):
        source_discovery = (self.agent_manager.discover(self._discovery,
                                                        discovery_cache)
                            if self._discovery else [])

        if self._resources:
            static_resources_group = self.agent_manager.construct_group_id(
                hash_of_set(self._resources))
            return [v for v in self._resources if
                    not self.agent_manager.partition_coordinator or
                    self.agent_manager.hashrings[
                        static_resources_group].belongs_to_self(
                            six.text_type(v))] + source_discovery

        return source_discovery

    @staticmethod
    def key(source_name, pollster):
        return '%s-%s' % (source_name, pollster.name)


def iter_random(iterable):
    """Iter over iterable in a random fashion."""
    lst = list(iterable)
    random.shuffle(lst)
    return iter(lst)


class PollingTask(object):
    """Polling task for polling samples and notifying.

    A polling task can be invoked periodically or only once.
    """

    def __init__(self, agent_manager):
        self.manager = agent_manager

        # elements of the Cartesian product of sources X pollsters
        # with a common interval
        self.pollster_matches = collections.defaultdict(set)

        # we relate the static resources and per-source discovery to
        # each combination of pollster and matching source
        resource_factory = lambda: Resources(agent_manager)
        self.resources = collections.defaultdict(resource_factory)

        self._batch = self.manager.conf.batch_polled_samples
        self._batch_size = self.manager.conf.polling.batch_size

        if not self._batch:
            # Support deprecated way of disabling baching
            self._batch_size = 0

        self._telemetry_secret = self.manager.conf.publisher.telemetry_secret

    def add(self, pollster, source):
        self.pollster_matches[source.name].add(pollster)
        key = Resources.key(source.name, pollster)
        self.resources[key].setup(source)

    def poll_and_notify(self):
        """Polling sample and notify."""
        cache = {}
        discovery_cache = {}
        poll_history = {}
        for source_name, pollsters in iter_random(
                self.pollster_matches.items()):
            for pollster in iter_random(pollsters):
                key = Resources.key(source_name, pollster)
                candidate_res = list(
                    self.resources[key].get(discovery_cache))
                if not candidate_res and pollster.obj.default_discovery:
                    candidate_res = self.manager.discover(
                        [pollster.obj.default_discovery], discovery_cache)

                # Remove duplicated resources and black resources. Using
                # set() requires well defined __hash__ for each resource.
                # Since __eq__ is defined, 'not in' is safe here.
                polling_resources = []
                black_res = self.resources[key].blacklist
                history = poll_history.get(pollster.name, [])
                for x in candidate_res:
                    if x not in history:
                        history.append(x)
                        if x not in black_res:
                            polling_resources.append(x)
                poll_history[pollster.name] = history

                # If no resources, skip for this pollster
                if not polling_resources:
                    p_context = 'new ' if history else ''
                    LOG.debug("Skip pollster %(name)s, no %(p_context)s"
                              "resources found this cycle",
                              {'name': pollster.name, 'p_context': p_context})
                    continue

                LOG.info("Polling pollster %(poll)s in the context of "
                         "%(src)s",
                         dict(poll=pollster.name, src=source_name))
                try:
                    polling_timestamp = timeutils.utcnow().isoformat()
                    samples = pollster.obj.get_samples(
                        manager=self.manager,
                        cache=cache,
                        resources=polling_resources
                    )
                    sample_batch = []

                    for sample in samples:
                        # Note(yuywz): Unify the timestamp of polled samples
                        sample.set_timestamp(polling_timestamp)
                        sample_dict = (
                            publisher_utils.meter_message_from_counter(
                                sample, self._telemetry_secret
                            ))
                        if self._batch_size:
                            if len(sample_batch) >= self._batch_size:
                                self._send_notification(sample_batch)
                                sample_batch = []
                            sample_batch.append(sample_dict)
                        else:
                            self._send_notification([sample_dict])

                    if sample_batch:
                        self._send_notification(sample_batch)

                except plugin_base.PollsterPermanentError as err:
                    LOG.error(
                        'Prevent pollster %(name)s from '
                        'polling %(res_list)s on source %(source)s anymore!',
                        dict(name=pollster.name,
                             res_list=str(err.fail_res_list),
                             source=source_name))
                    self.resources[key].blacklist.extend(err.fail_res_list)
                except Exception as err:
                    LOG.error(
                        'Continue after error from %(name)s: %(error)s'
                        % ({'name': pollster.name, 'error': err}),
                        exc_info=True)

    def _send_notification(self, samples):
        self.manager.notifier.sample(
            {},
            'telemetry.polling',
            {'samples': samples}
        )


class AgentManager(cotyledon.Service):

    def __init__(self, worker_id, conf, namespaces=None):
        namespaces = namespaces or ['compute', 'central']
        group_prefix = conf.polling.partitioning_group_prefix

        super(AgentManager, self).__init__(worker_id)

        self.conf = conf

        if type(namespaces) is not list:
            namespaces = [namespaces]

        # we'll have default ['compute', 'central'] here if no namespaces will
        # be passed
        extensions = (self._extensions('poll', namespace, self.conf).extensions
                      for namespace in namespaces)
        # get the extensions from pollster builder
        extensions_fb = (self._extensions_from_builder('poll', namespace)
                         for namespace in namespaces)

        self.extensions = list(itertools.chain(*list(extensions))) + list(
            itertools.chain(*list(extensions_fb)))

        if not self.extensions:
            LOG.warning('No valid pollsters can be loaded from %s '
                        'namespaces', namespaces)

        discoveries = (self._extensions('discover', namespace,
                                        self.conf).extensions
                       for namespace in namespaces)
        self.discoveries = list(itertools.chain(*list(discoveries)))
        self.polling_periodics = None

        self.hashrings = None
        self.partition_coordinator = None
        if self.conf.coordination.backend_url:
            # XXX uuid4().bytes ought to work, but it requires ascii for now
            coordination_id = str(uuid.uuid4()).encode('ascii')
            self.partition_coordinator = coordination.get_coordinator(
                self.conf.coordination.backend_url, coordination_id)

        # Compose coordination group prefix.
        # We'll use namespaces as the basement for this partitioning.
        namespace_prefix = '-'.join(sorted(namespaces))
        self.group_prefix = ('%s-%s' % (namespace_prefix, group_prefix)
                             if group_prefix else namespace_prefix)

        self.notifier = oslo_messaging.Notifier(
            messaging.get_transport(self.conf),
            driver=self.conf.publisher_notifier.telemetry_driver,
            publisher_id="ceilometer.polling")

        self._keystone = None
        self._keystone_last_exception = None

    @staticmethod
    def _get_ext_mgr(namespace, *args, **kwargs):
        def _catch_extension_load_error(mgr, ep, exc):
            # Extension raising ExtensionLoadError can be ignored,
            # and ignore anything we can't import as a safety measure.
            if isinstance(exc, plugin_base.ExtensionLoadError):
                LOG.debug("Skip loading extension for %s: %s",
                          ep.name, exc.msg)
                return

            show_exception = (LOG.isEnabledFor(logging.DEBUG)
                              and isinstance(exc, ImportError))
            LOG.error("Failed to import extension for %(name)r: "
                      "%(error)s",
                      {'name': ep.name, 'error': exc},
                      exc_info=show_exception)
            if isinstance(exc, ImportError):
                return
            raise exc

        return extension.ExtensionManager(
            namespace=namespace,
            invoke_on_load=True,
            invoke_args=args,
            invoke_kwds=kwargs,
            on_load_failure_callback=_catch_extension_load_error,
        )

    def _extensions(self, category, agent_ns=None, *args, **kwargs):
        namespace = ('ceilometer.%s.%s' % (category, agent_ns) if agent_ns
                     else 'ceilometer.%s' % category)
        return self._get_ext_mgr(namespace, *args, **kwargs)

    def _extensions_from_builder(self, category, agent_ns=None):
        ns = ('ceilometer.builder.%s.%s' % (category, agent_ns) if agent_ns
              else 'ceilometer.builder.%s' % category)
        mgr = self._get_ext_mgr(ns, self.conf)

        def _build(ext):
            return ext.plugin.get_pollsters_extensions(self.conf)

        # NOTE: this seems a stevedore bug. if no extensions are found,
        # map will raise runtimeError which is not documented.
        if mgr.names():
            return list(itertools.chain(*mgr.map(_build)))
        else:
            return []

    def join_partitioning_groups(self):
        groups = set([self.construct_group_id(d.obj.group_id)
                      for d in self.discoveries])
        # let each set of statically-defined resources have its own group
        static_resource_groups = set([
            self.construct_group_id(hash_of_set(p.resources))
            for p in self.polling_manager.sources
            if p.resources
        ])
        groups.update(static_resource_groups)

        self.hashrings = dict(
            (group, self.partition_coordinator.join_partitioned_group(group))
            for group in groups)

    def setup_polling_tasks(self):
        polling_tasks = {}
        for source in self.polling_manager.sources:
            for pollster in self.extensions:
                if source.support_meter(pollster.name):
                    polling_task = polling_tasks.get(source.get_interval())
                    if not polling_task:
                        polling_task = PollingTask(self)
                        polling_tasks[source.get_interval()] = polling_task
                    polling_task.add(pollster, source)
        return polling_tasks

    def construct_group_id(self, discovery_group_id):
        return '%s-%s' % (self.group_prefix, discovery_group_id)

    def start_polling_tasks(self):
        data = self.setup_polling_tasks()

        # Don't start useless threads if no task will run
        if not data:
            return

        # One thread per polling tasks is enough
        self.polling_periodics = periodics.PeriodicWorker.create(
            [], executor_factory=lambda:
            futures.ThreadPoolExecutor(max_workers=len(data)))

        for interval, polling_task in data.items():

            @periodics.periodic(spacing=interval, run_immediately=True)
            def task(running_task):
                self.interval_task(running_task)

            self.polling_periodics.add(task, polling_task)

        utils.spawn_thread(self.polling_periodics.start, allow_empty=True)

    def run(self):
        super(AgentManager, self).run()
        self.polling_manager = PollingManager(self.conf)
        if self.partition_coordinator:
            self.partition_coordinator.start(start_heart=True)
            self.join_partitioning_groups()
        self.start_polling_tasks()

    def terminate(self):
        self.stop_pollsters_tasks()
        if self.partition_coordinator:
            self.partition_coordinator.stop()
        super(AgentManager, self).terminate()

    def interval_task(self, task):
        # NOTE(sileht): remove the previous keystone client
        # and exception to get a new one in this polling cycle.
        self._keystone = None
        self._keystone_last_exception = None

        # Note(leehom): if coordinator enabled call run_watchers to
        # update group member info before collecting
        if self.partition_coordinator:
            self.partition_coordinator.run_watchers()

        task.poll_and_notify()

    @property
    def keystone(self):
        # FIXME(sileht): This lazy loading of keystone client doesn't
        # look concurrently safe, we never see issue because once we have
        # connected to keystone everything is fine, and because all pollsters
        # are delayed during startup. But each polling task creates a new
        # client and overrides it which has been created by other polling
        # tasks. During this short time bad thing can occur.
        #
        # I think we must not reset keystone client before
        # running a polling task, but refresh it periodically instead.

        # NOTE(sileht): we do lazy loading of the keystone client
        # for multiple reasons:
        # * don't use it if no plugin need it
        # * use only one client for all plugins per polling cycle
        if self._keystone is None and self._keystone_last_exception is None:
            try:
                self._keystone = keystone_client.get_client(self.conf)
                self._keystone_last_exception = None
            except ka_exceptions.ClientException as e:
                self._keystone = None
                self._keystone_last_exception = e
        if self._keystone is not None:
            return self._keystone
        else:
            raise self._keystone_last_exception

    @staticmethod
    def _parse_discoverer(url):
        s = urlparse.urlparse(url)
        return (s.scheme or s.path), (s.netloc + s.path if s.scheme else None)

    def _discoverer(self, name):
        for d in self.discoveries:
            if d.name == name:
                return d.obj
        return None

    def discover(self, discovery=None, discovery_cache=None):
        resources = []
        discovery = discovery or []
        for url in discovery:
            if discovery_cache is not None and url in discovery_cache:
                resources.extend(discovery_cache[url])
                continue
            name, param = self._parse_discoverer(url)
            discoverer = self._discoverer(name)
            if discoverer:
                try:
                    if discoverer.KEYSTONE_REQUIRED_FOR_SERVICE:
                        service_type = getattr(
                            self.conf.service_types,
                            discoverer.KEYSTONE_REQUIRED_FOR_SERVICE)
                        if not keystone_client.get_service_catalog(
                                self.keystone).get_endpoints(
                                    service_type=service_type):
                            LOG.warning(
                                'Skipping %(name)s, %(service_type)s service '
                                'is not registered in keystone',
                                {'name': name, 'service_type': service_type})
                            continue

                    discovered = discoverer.discover(self, param)

                    if self.partition_coordinator:
                        discovered = [
                            v for v in discovered if self.hashrings[
                                self.construct_group_id(discoverer.group_id)
                            ].belongs_to_self(six.text_type(v))]

                    resources.extend(discovered)
                    if discovery_cache is not None:
                        discovery_cache[url] = discovered
                except ka_exceptions.ClientException as e:
                    LOG.error('Skipping %(name)s, keystone issue: '
                              '%(exc)s', {'name': name, 'exc': e})
                except Exception as err:
                    LOG.exception('Unable to discover resources: %s', err)
            else:
                LOG.warning('Unknown discovery extension: %s', name)
        return resources

    def stop_pollsters_tasks(self):
        if self.polling_periodics:
            self.polling_periodics.stop()
            self.polling_periodics.wait()
        self.polling_periodics = None


class PollingManager(agent.ConfigManagerBase):
    """Polling Manager to handle polling definition"""

    def __init__(self, conf):
        """Setup the polling according to config.

        The configuration is supported as follows:

        {"sources": [{"name": source_1,
                      "interval": interval_time,
                      "meters" : ["meter_1", "meter_2"],
                      "resources": ["resource_uri1", "resource_uri2"],
                     },
                     {"name": source_2,
                      "interval": interval_time,
                      "meters" : ["meter_3"],
                     },
                    ]}
        }

        The interval determines the cadence of sample polling

        Valid meter format is '*', '!meter_name', or 'meter_name'.
        '*' is wildcard symbol means any meters; '!meter_name' means
        "meter_name" will be excluded; 'meter_name' means 'meter_name'
        will be included.

        Valid meters definition is all "included meter names", all
        "excluded meter names", wildcard and "excluded meter names", or
        only wildcard.

        The resources is list of URI indicating the resources from where
        the meters should be polled. It's optional and it's up to the
        specific pollster to decide how to use it.

        """
        super(PollingManager, self).__init__(conf)
        cfg = self.load_config(conf.polling.cfg_file)
        self.sources = []
        if 'sources' not in cfg:
            raise PollingException("sources required", cfg)
        for s in cfg.get('sources'):
            self.sources.append(PollingSource(s))


class PollingSource(agent.Source):
    """Represents a source of pollsters

    In effect it is a set of pollsters emitting
    samples for a set of matching meters. Each source encapsulates meter name
    matching, polling interval determination, optional resource enumeration or
    discovery.
    """

    def __init__(self, cfg):
        try:
            super(PollingSource, self).__init__(cfg)
        except agent.SourceException as err:
            raise PollingException(err.msg, cfg)
        try:
            self.meters = cfg['meters']
        except KeyError:
            raise PollingException("Missing meters value", cfg)
        try:
            self.interval = int(cfg['interval'])
        except ValueError:
            raise PollingException("Invalid interval value", cfg)
        except KeyError:
            raise PollingException("Missing interval value", cfg)
        if self.interval <= 0:
            raise PollingException("Interval value should > 0", cfg)

        self.resources = cfg.get('resources') or []
        if not isinstance(self.resources, list):
            raise PollingException("Resources should be a list", cfg)

        self.discovery = cfg.get('discovery') or []
        if not isinstance(self.discovery, list):
            raise PollingException("Discovery should be a list", cfg)
        try:
            self.check_source_filtering(self.meters, 'meters')
        except agent.SourceException as err:
            raise PollingException(err.msg, cfg)

    def get_interval(self):
        return self.interval

    def support_meter(self, meter_name):
        return self.is_supported(self.meters, meter_name)
