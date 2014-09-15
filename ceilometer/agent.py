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
import itertools

from oslo.config import cfg
import six
from six.moves.urllib import parse as urlparse
from stevedore import extension

from ceilometer import coordination
from ceilometer.openstack.common import context
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer.openstack.common import service as os_service
from ceilometer import pipeline as publish_pipeline
from ceilometer import utils

LOG = log.getLogger(__name__)

cfg.CONF.import_opt('heartbeat', 'ceilometer.coordination',
                    group='coordination')


class Resources(object):
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        self._resources = []
        self._discovery = []

    def setup(self, pipeline):
        self._resources = pipeline.resources
        self._discovery = pipeline.discovery

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
    def key(source, pollster):
        return '%s-%s' % (source.name, pollster.name)


class PollingTask(object):
    """Polling task for polling samples and inject into pipeline.

    A polling task can be invoked periodically or only once.
    """

    def __init__(self, agent_manager):
        self.manager = agent_manager

        # elements of the Cartesian product of sources X pollsters
        # with a common interval
        self.pollster_matches = set()

        # per-sink publisher contexts associated with each source
        self.publishers = {}

        # we relate the static resources and per-source discovery to
        # each combination of pollster and matching source
        resource_factory = lambda: Resources(agent_manager)
        self.resources = collections.defaultdict(resource_factory)

    def add(self, pollster, pipeline):
        if pipeline.source.name not in self.publishers:
            publish_context = publish_pipeline.PublishContext(
                self.manager.context)
            self.publishers[pipeline.source.name] = publish_context
        self.publishers[pipeline.source.name].add_pipelines([pipeline])
        self.pollster_matches.update([(pipeline.source, pollster)])
        key = Resources.key(pipeline.source, pollster)
        self.resources[key].setup(pipeline)

    def poll_and_publish(self):
        """Polling sample and publish into pipeline."""
        agent_resources = self.manager.discover()
        cache = {}
        discovery_cache = {}
        for source, pollster in self.pollster_matches:
            LOG.info(_("Polling pollster %(poll)s in the context of %(src)s"),
                     dict(poll=pollster.name, src=source))
            pollster_resources = None
            if pollster.obj.default_discovery:
                pollster_resources = self.manager.discover(
                    [pollster.obj.default_discovery], discovery_cache)
            key = Resources.key(source, pollster)
            source_resources = list(self.resources[key].get(discovery_cache))
            with self.publishers[source.name] as publisher:
                try:
                    samples = list(pollster.obj.get_samples(
                        manager=self.manager,
                        cache=cache,
                        resources=(source_resources or
                                   pollster_resources or
                                   agent_resources)
                    ))
                    publisher(samples)
                except Exception as err:
                    LOG.warning(_(
                        'Continue after error from %(name)s: %(error)s')
                        % ({'name': pollster.name, 'error': err}),
                        exc_info=True)


class AgentManager(os_service.Service):

    def __init__(self, namespace, default_discovery=None, group_prefix=None):
        super(AgentManager, self).__init__()
        default_discovery = default_discovery or []
        self.default_discovery = default_discovery
        self.pollster_manager = self._extensions('poll', namespace)
        self.discovery_manager = self._extensions('discover')
        self.context = context.RequestContext('admin', 'admin', is_admin=True)
        self.partition_coordinator = coordination.PartitionCoordinator()
        self.group_prefix = ('%s-%s' % (namespace, group_prefix)
                             if group_prefix else namespace)

    @staticmethod
    def _extensions(category, agent_ns=None):
        namespace = ('ceilometer.%s.%s' % (category, agent_ns) if agent_ns
                     else 'ceilometer.%s' % category)
        return extension.ExtensionManager(
            namespace=namespace,
            invoke_on_load=True,
        )

    def join_partitioning_groups(self):
        groups = set([self.construct_group_id(d.obj.group_id)
                      for d in self.discovery_manager])
        # let each set of statically-defined resources have its own group
        static_resource_groups = set([
            self.construct_group_id(utils.hash_of_set(p.resources))
            for p in self.pipeline_manager.pipelines
            if p.resources
        ])
        groups.update(static_resource_groups)
        for group in groups:
            self.partition_coordinator.join_group(group)

    def create_polling_task(self):
        """Create an initially empty polling task."""
        return PollingTask(self)

    def setup_polling_tasks(self):
        polling_tasks = {}
        for pipeline, pollster in itertools.product(
                self.pipeline_manager.pipelines,
                self.pollster_manager.extensions):
            if pipeline.support_meter(pollster.name):
                polling_task = polling_tasks.get(pipeline.get_interval())
                if not polling_task:
                    polling_task = self.create_polling_task()
                    polling_tasks[pipeline.get_interval()] = polling_task
                polling_task.add(pollster, pipeline)

        return polling_tasks

    def construct_group_id(self, discovery_group_id):
        return ('%s-%s' % (self.group_prefix,
                           discovery_group_id)
                if discovery_group_id else None)

    def start(self):
        self.pipeline_manager = publish_pipeline.setup_pipeline()

        self.partition_coordinator.start()
        self.join_partitioning_groups()

        # allow time for coordination if necessary
        delay_start = self.partition_coordinator.is_active()

        for interval, task in six.iteritems(self.setup_polling_tasks()):
            self.tg.add_timer(interval,
                              self.interval_task,
                              initial_delay=interval if delay_start else None,
                              task=task)
        self.tg.add_timer(cfg.CONF.coordination.heartbeat,
                          self.partition_coordinator.heartbeat)

    @staticmethod
    def interval_task(task):
        task.poll_and_publish()

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
        for url in (discovery or self.default_discovery):
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
