#
# Copyright 2013 Julien Danjou
# Copyright 2014 Red Hat, Inc
#
# Authors: Julien Danjou <julien@danjou.info>
#          Eoghan Glynn <eglynn@redhat.com>
#          Nejc Saje <nsaje@redhat.com>
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
import fnmatch
import itertools
import random

from oslo_config import cfg
from oslo_context import context
from oslo_log import log
import oslo_messaging
from six import moves
from six.moves.urllib import parse as urlparse
from stevedore import extension

from ceilometer.agent import plugin_base
from ceilometer import coordination
from ceilometer.i18n import _, _LI
from ceilometer import messaging
from ceilometer import pipeline
from ceilometer.publisher import utils as publisher_utils
from ceilometer import service_base
from ceilometer import utils

LOG = log.getLogger(__name__)

OPTS = [
    cfg.BoolOpt('batch_polled_samples',
                default=True,
                help='To reduce polling agent load, samples are sent to the '
                     'notification agent in a batch. To gain higher '
                     'throughput at the cost of load set this to False.'),
    cfg.IntOpt('shuffle_time_before_polling_task',
               default=0,
               help='To reduce large requests at same time to Nova or other '
                    'components from different compute agents, shuffle '
                    'start time of polling task.'),
]

cfg.CONF.register_opts(OPTS)
cfg.CONF.import_opt('telemetry_driver', 'ceilometer.publisher.messaging',
                    group='publisher_notifier')


class PollsterListForbidden(Exception):
    def __init__(self):
        msg = ('It is forbidden to use pollster-list option of polling agent '
               'in case of using coordination between multiple agents. Please '
               'use either multiple agents being coordinated or polling list '
               'option for one polling agent.')
        super(PollsterListForbidden, self).__init__(msg)


class Resources(object):
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        self._resources = []
        self._discovery = []
        self.blacklist = []
        self.last_dup = []

    def setup(self, source):
        self._resources = source.resources
        self._discovery = source.discovery

    def get(self, discovery_cache=None):
        source_discovery = (self.agent_manager.discover(self._discovery,
                                                        discovery_cache)
                            if self._discovery else [])
        static_resources = []
        if self._resources:
            static_resources_group = self.agent_manager.construct_group_id(
                utils.hash_of_set(self._resources))
            p_coord = self.agent_manager.partition_coordinator
            static_resources = p_coord.extract_my_subset(
                static_resources_group, self._resources)
        return static_resources + source_discovery

    @staticmethod
    def key(source_name, pollster):
        return '%s-%s' % (source_name, pollster.name)


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

        if cfg.CONF.batch_polled_samples:
            self._handle_sample = self._assemble_samples
        else:
            self._handle_sample = self._send_notification
        self._telemetry_secret = cfg.CONF.publisher.telemetry_secret

    def add(self, pollster, source):
        self.pollster_matches[source.name].add(pollster)
        key = Resources.key(source.name, pollster)
        self.resources[key].setup(source)

    def poll_and_notify(self):
        """Polling sample and notify."""
        cache = {}
        discovery_cache = {}
        for source_name in self.pollster_matches:
            for pollster in self.pollster_matches[source_name]:
                LOG.info(_("Polling pollster %(poll)s in the context of "
                           "%(src)s"),
                         dict(poll=pollster.name, src=source_name))
                key = Resources.key(source_name, pollster)
                candidate_res = list(
                    self.resources[key].get(discovery_cache))
                if not candidate_res and pollster.obj.default_discovery:
                    candidate_res = self.manager.discover(
                        [pollster.obj.default_discovery], discovery_cache)

                # Remove duplicated resources and black resources. Using
                # set() requires well defined __hash__ for each resource.
                # Since __eq__ is defined, 'not in' is safe here.
                seen = []
                duplicated = []
                polling_resources = []
                black_res = self.resources[key].blacklist
                for x in candidate_res:
                    if x not in seen:
                        seen.append(x)
                        if x not in black_res:
                            polling_resources.append(x)
                    else:
                        duplicated.append(x)

                # Warn duplicated resources for the 1st time
                if self.resources[key].last_dup != duplicated:
                    self.resources[key].last_dup = duplicated
                    LOG.warning(_(
                        'Found following duplicated resoures for '
                        '%(name)s in context of %(source)s:%(list)s. '
                        'Check pipeline configuration.')
                        % ({'name': pollster.name,
                            'source': source_name,
                            'list': duplicated
                            }))

                # If no resources, skip for this pollster
                if not polling_resources:
                    LOG.info(_("Skip polling pollster %s, no resources"
                               " found"), pollster.name)
                    continue

                try:
                    samples = pollster.obj.get_samples(
                        manager=self.manager,
                        cache=cache,
                        resources=polling_resources
                    )
                    sample_batch = []

                    for sample in samples:
                        sample_dict = (
                            publisher_utils.meter_message_from_counter(
                                sample, self._telemetry_secret
                            ))
                        self._handle_sample([sample_dict], sample_batch)

                    # sample_batch will contain samples if
                    # cfg.CONF.batch_polled_samples is True
                    if sample_batch:
                        self._send_notification(sample_batch)

                except plugin_base.PollsterPermanentError as err:
                    LOG.error(_(
                        'Prevent pollster %(name)s for '
                        'polling source %(source)s anymore!')
                        % ({'name': pollster.name, 'source': source_name}))
                    self.resources[key].blacklist.append(err.fail_res)
                except Exception as err:
                    LOG.warning(_(
                        'Continue after error from %(name)s: %(error)s')
                        % ({'name': pollster.name, 'error': err}),
                        exc_info=True)

    @staticmethod
    def _assemble_samples(samples, batch):
        batch.extend(samples)

    def _send_notification(self, samples, batch=None):
        self.manager.notifier.info(
            self.manager.context.to_dict(),
            'telemetry.api',
            samples
        )


class AgentManager(service_base.BaseService):

    def __init__(self, namespaces, pollster_list, group_prefix=None):
        # features of using coordination and pollster-list are exclusive, and
        # cannot be used at one moment to avoid both samples duplication and
        # samples being lost
        if pollster_list and cfg.CONF.coordination.backend_url:
            raise PollsterListForbidden()

        super(AgentManager, self).__init__()

        def _match(pollster):
            """Find out if pollster name matches to one of the list."""
            return any(fnmatch.fnmatch(pollster.name, pattern) for
                       pattern in pollster_list)

        if type(namespaces) is not list:
            namespaces = [namespaces]

        # we'll have default ['compute', 'central'] here if no namespaces will
        # be passed
        extensions = (self._extensions('poll', namespace).extensions
                      for namespace in namespaces)
        if pollster_list:
            extensions = (moves.filter(_match, exts)
                          for exts in extensions)

        self.extensions = list(itertools.chain(*list(extensions)))

        self.discovery_manager = self._extensions('discover')
        self.context = context.RequestContext('admin', 'admin', is_admin=True)
        self.partition_coordinator = coordination.PartitionCoordinator()

        # Compose coordination group prefix.
        # We'll use namespaces as the basement for this partitioning.
        namespace_prefix = '-'.join(sorted(namespaces))
        self.group_prefix = ('%s-%s' % (namespace_prefix, group_prefix)
                             if group_prefix else namespace_prefix)

        self.notifier = oslo_messaging.Notifier(
            messaging.get_transport(),
            driver=cfg.CONF.publisher_notifier.telemetry_driver,
            publisher_id="ceilometer.api")

    @staticmethod
    def _extensions(category, agent_ns=None):
        namespace = ('ceilometer.%s.%s' % (category, agent_ns) if agent_ns
                     else 'ceilometer.%s' % category)

        def _catch_extension_load_error(mgr, ep, exc):
            # Extension raising ExtensionLoadError can be ignored,
            # and ignore anything we can't import as a safety measure.
            if isinstance(exc, plugin_base.ExtensionLoadError):
                LOG.error(_("Skip loading extension for %s") % ep.name)
                return
            if isinstance(exc, ImportError):
                LOG.error(
                    _("Failed to import extension for %(name)s: %(error)s"),
                    {'name': ep.name, 'error': exc},
                )
                return
            raise exc

        return extension.ExtensionManager(
            namespace=namespace,
            invoke_on_load=True,
            on_load_failure_callback=_catch_extension_load_error,
        )

    def join_partitioning_groups(self):
        self.groups = set([self.construct_group_id(d.obj.group_id)
                          for d in self.discovery_manager])
        # let each set of statically-defined resources have its own group
        static_resource_groups = set([
            self.construct_group_id(utils.hash_of_set(p.resources))
            for p in self.polling_manager.sources
            if p.resources
        ])
        self.groups.update(static_resource_groups)
        for group in self.groups:
            self.partition_coordinator.join_group(group)

    def create_polling_task(self):
        """Create an initially empty polling task."""
        return PollingTask(self)

    def setup_polling_tasks(self):
        polling_tasks = {}
        for source in self.polling_manager.sources:
            polling_task = None
            for pollster in self.extensions:
                if source.support_meter(pollster.name):
                    polling_task = polling_tasks.get(source.get_interval())
                    if not polling_task:
                        polling_task = self.create_polling_task()
                        polling_tasks[source.get_interval()] = polling_task
                    polling_task.add(pollster, source)
        return polling_tasks

    def construct_group_id(self, discovery_group_id):
        return ('%s-%s' % (self.group_prefix,
                           discovery_group_id)
                if discovery_group_id else None)

    def configure_polling_tasks(self):
        # allow time for coordination if necessary
        delay_start = self.partition_coordinator.is_active()

        # set shuffle time before polling task if necessary
        delay_polling_time = random.randint(
            0, cfg.CONF.shuffle_time_before_polling_task)

        pollster_timers = []
        data = self.setup_polling_tasks()
        for interval, polling_task in data.items():
            delay_time = (interval + delay_polling_time if delay_start
                          else delay_polling_time)
            pollster_timers.append(self.tg.add_timer(interval,
                                   self.interval_task,
                                   initial_delay=delay_time,
                                   task=polling_task))
        self.tg.add_timer(cfg.CONF.coordination.heartbeat,
                          self.partition_coordinator.heartbeat)

        return pollster_timers

    def start(self):
        self.polling_manager = pipeline.setup_polling()

        self.partition_coordinator.start()
        self.join_partitioning_groups()

        self.pollster_timers = self.configure_polling_tasks()

        self.init_pipeline_refresh()

    def stop(self):
        if self.partition_coordinator:
            self.partition_coordinator.stop()
        super(AgentManager, self).stop()

    @staticmethod
    def interval_task(task):
        task.poll_and_notify()

    @staticmethod
    def _parse_discoverer(url):
        s = urlparse.urlparse(url)
        return (s.scheme or s.path), (s.netloc + s.path if s.scheme else None)

    def _discoverer(self, name):
        for d in self.discovery_manager:
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
                    discovered = discoverer.discover(self, param)
                    partitioned = self.partition_coordinator.extract_my_subset(
                        self.construct_group_id(discoverer.group_id),
                        discovered)
                    resources.extend(partitioned)
                    if discovery_cache is not None:
                        discovery_cache[url] = partitioned
                except Exception as err:
                    LOG.exception(_('Unable to discover resources: %s') % err)
            else:
                LOG.warning(_('Unknown discovery extension: %s') % name)
        return resources

    def stop_pollsters(self):
        for x in self.pollster_timers:
            try:
                x.stop()
                self.tg.timer_done(x)
            except Exception:
                LOG.error(_('Error stopping pollster.'), exc_info=True)
        self.pollster_timers = []

    def reload_pipeline(self):
        LOG.info(_LI("Reconfiguring polling tasks."))

        # stop existing pollsters and leave partitioning groups
        self.stop_pollsters()
        for group in self.groups:
            self.partition_coordinator.leave_group(group)

        # re-create partitioning groups according to pipeline
        # and configure polling tasks with latest pipeline conf
        self.join_partitioning_groups()
        self.pollster_timers = self.configure_polling_tasks()
