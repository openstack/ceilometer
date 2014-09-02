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
from ceilometer import pipeline

LOG = log.getLogger(__name__)

cfg.CONF.import_opt('heartbeat', 'ceilometer.coordination',
                    group='coordination')


class Resources(object):
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        self._resources = []
        self._discovery = set([])

    def extend(self, pipeline):
        self._resources.extend(pipeline.resources)
        self._discovery.update(set(pipeline.discovery))

    @property
    def resources(self):
        source_discovery = (self.agent_manager.discover(self._discovery)
                            if self._discovery else [])
        return self._resources + source_discovery


class PollingTask(object):
    """Polling task for polling samples and inject into pipeline.

    A polling task can be invoked periodically or only once.
    """

    def __init__(self, agent_manager):
        self.manager = agent_manager
        self.pollsters = set()
        # we extend the amalgamation of all static resources for this
        # set of pollsters with a common interval, so as to also
        # include any dynamically discovered resources specific to
        # the matching pipelines (if either is present, the per-agent
        # default discovery is overridden)
        resource_factory = lambda: Resources(agent_manager)
        self.resources = collections.defaultdict(resource_factory)
        self.publish_context = pipeline.PublishContext(
            agent_manager.context)

    def add(self, pollster, pipelines):
        self.publish_context.add_pipelines(pipelines)
        for pipe_line in pipelines:
            self.resources[pollster.name].extend(pipe_line)
        self.pollsters.update([pollster])

    def poll_and_publish(self):
        """Polling sample and publish into pipeline."""
        agent_resources = self.manager.discover()
        with self.publish_context as publisher:
            cache = {}
            for pollster in self.pollsters:
                key = pollster.name
                LOG.info(_("Polling pollster %s"), key)
                source_resources = list(self.resources[key].resources)
                try:
                    samples = list(pollster.obj.get_samples(
                        manager=self.manager,
                        cache=cache,
                        resources=source_resources or agent_resources,
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
        groups = set([self._construct_group_id(d.obj.group_id)
                      for d in self.discovery_manager])
        for group in groups:
            self.partition_coordinator.join_group(group)

    def create_polling_task(self):
        """Create an initially empty polling task."""
        return PollingTask(self)

    def setup_polling_tasks(self):
        polling_tasks = {}
        for pipe_line, pollster in itertools.product(
                self.pipeline_manager.pipelines,
                self.pollster_manager.extensions):
            if pipe_line.support_meter(pollster.name):
                polling_task = polling_tasks.get(pipe_line.get_interval())
                if not polling_task:
                    polling_task = self.create_polling_task()
                    polling_tasks[pipe_line.get_interval()] = polling_task
                polling_task.add(pollster, [pipe_line])

        return polling_tasks

    def _construct_group_id(self, discovery_group_id):
        return ('%s-%s' % (self.group_prefix,
                           discovery_group_id)
                if discovery_group_id else None)

    def start(self):
        self.pipeline_manager = pipeline.setup_pipeline()

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

    def discover(self, discovery=None):
        resources = []
        for url in (discovery or self.default_discovery):
            name, param = self._parse_discoverer(url)
            discoverer = self._discoverer(name)
            if discoverer:
                try:
                    discovered = discoverer.discover(param)
                    partitioned = self.partition_coordinator.extract_my_subset(
                        self._construct_group_id(discoverer.group_id),
                        discovered)
                    resources.extend(partitioned)
                except Exception as err:
                    LOG.exception(_('Unable to discover resources: %s') % err)
            else:
                LOG.warning(_('Unknown discovery extension: %s') % name)
        return resources
