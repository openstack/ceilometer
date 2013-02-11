# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Intel Corp.
#
# Author: Yunhong Jiang <yunhong.jiang@intel.com>
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

import os

from stevedore import extension
import yaml

from ceilometer.openstack.common import cfg
from ceilometer.openstack.common import log

OPTS = [
    cfg.StrOpt('pipeline_cfg_file',
               default="pipeline.yaml",
               help="Configuration file for pipeline definition"
               ),
]

cfg.CONF.register_opts(OPTS)

LOG = log.getLogger(__name__)

PUBLISHER_NAMESPACE = 'ceilometer.publisher'
TRANSFORMER_NAMESPACE = 'ceilometer.transformer'


class PipelineException(Exception):
    def __init__(self, message, pipeline_cfg):
        self.msg = message
        self.pipeline_cfg = pipeline_cfg

    def __str__(self):
        return 'Pipeline %s: %s' % (self.pipeline_cfg, self.msg)


class TransformerExtensionManager(extension.ExtensionManager):

    def __init__(self):
        super(TransformerExtensionManager, self).__init__(
            namespace=TRANSFORMER_NAMESPACE,
            invoke_on_load=False,
            invoke_args=(),
            invoke_kwds={}
        )
        self.by_name = dict((e.name, e) for e in self.extensions)

    def get_ext(self, name):
        return self.by_name[name]


class Pipeline(object):
    """Sample handling pipeline

    Pipeline describes a chain of handlers. The chain starts with
    tranformer and ends with one or more publishers.

    The first transformer in the chain gets counter from data collector, i.e.
    pollster or notification handler, takes some action like dropping,
    aggregation, changing field etc, then passes the updated counter
    to next step.

    The subsequent transformers, if any, handle the data similarly.

    In the end of the chain, publishers publish the data. The exact publishing
    method depends on publisher type, for example, pushing into data storage
    through message bus, sending to external CW software through CW API call.

    If no transformer is included in the chain, the publishers get counters
    from data collector and publish them directly.

    """

    def __init__(self, cfg, publisher_manager, transformer_manager):
        self.cfg = cfg

        try:
            self.name = cfg['name']
            try:
                self.interval = int(cfg['interval'])
            except ValueError:
                raise PipelineException("Invalid interval value", cfg)
            self.counters = cfg['counters']
            self.publishers = cfg['publishers']
            # It's legal to have no transformer specified
            self.transformer_cfg = cfg['transformers'] or []
            self.publisher_manager = publisher_manager
        except KeyError as err:
            raise PipelineException(
                "Required field %s not specified" % err.args[0], cfg)

        if self.interval <= 0:
            raise PipelineException("Interval value should > 0", cfg)

        self._check_counters()

        self._check_publishers(cfg, publisher_manager)

        self.transformers = self._setup_transformers(cfg, transformer_manager)

    def __str__(self):
        return self.name

    def _check_counters(self):
        """Counter rules checking

        At least one meaningful counter exist
        Included type and excluded type counter can't co-exist at
        the same pipeline
        Included type counter and wildcard can't co-exist at same pipeline

        """
        counters = self.counters
        if not counters:
            raise PipelineException("No counter specified", self.cfg)

        if [x for x in counters if x[0] not in '!*'] and \
           [x for x in counters if x[0] == '!']:
            raise PipelineException(
                "Both included and excluded counters specified",
                cfg)

        if '*' in counters and [x for x in counters if x[0] not in '!*']:
            raise PipelineException(
                "Included counters specified with wildcard",
                self.cfg)

    def _check_publishers(self, cfg, publisher_manager):
        if not self.publishers:
            raise PipelineException(
                "No publisher specified", cfg)
        if not set(self.publishers).issubset(set(publisher_manager.names())):
            raise PipelineException(
                "Publishers %s invalid" %
                set(self.publishers).difference(
                    set(self.publisher_manager.names())), cfg)

    def _setup_transformers(self, cfg, transformer_manager):
        transformer_cfg = cfg['transformers'] or []
        transformers = []
        for transformer in transformer_cfg:
            parameter = transformer['parameters'] or {}
            try:
                ext = transformer_manager.get_ext(transformer['name'])
            except KeyError:
                raise PipelineException(
                    "No transformer named %s loaded" % transformer['name'],
                    cfg)
            transformers.append(ext.plugin(**parameter))
            LOG.info("Pipeline %s: Setup transformer instance %s "
                     "with parameter %s",
                     self,
                     transformer['name'],
                     parameter)

        return transformers

    def _publish_counter_to_one_publisher(self, ext, ctxt, counter, source):
        try:
            ext.obj.publish_counter(ctxt, counter, source)
        except Exception as err:
            LOG.warning("Pipeline %s: Continue after error "
                        "from publisher %s for %s",
                        self, ext.name, counter)
            LOG.exception(err)

    def _transform_counter(self, start, ctxt, counter, source):
        try:
            for transformer in self.transformers[start:]:
                counter = transformer.handle_sample(ctxt, counter, source)
                if not counter:
                    LOG.debug("Pipeline %s: Counter dropped by transformer %s",
                              self, transformer)
                    return
            return counter
        except Exception as err:
            LOG.warning("Pipeline %s: Exit after error from transformer"
                        "%s for %s",
                        self, transformer, counter)
            LOG.exception(err)

    def _publish_counter(self, start, ctxt, counter, source):
        """Push counter into pipeline for publishing.

        param start: the first transformer that the counter will be injected.
                     This is mainly for flush() invocation that transformer
                     may emit counters
        param ctxt: execution context from the manager or service
        param counter: counter
        param source: counter source

        """
        LOG.audit("Pipeline %s: Transform counter %s from %s transformer",
                  self, counter, start)
        counter = self._transform_counter(start, ctxt, counter, source)
        if not counter:
            return

        LOG.audit("Pipeline %s: Publish counter %s", self, counter)
        self.publisher_manager.map(self.publishers,
                                   self._publish_counter_to_one_publisher,
                                   ctxt=ctxt,
                                   counter=counter,
                                   source=source,
                                   )

        LOG.audit("Pipeline %s: Published counter %s", self, counter)

    def publish_counter(self, ctxt, counter, source):
        if self.support_counter(counter.name):
            self._publish_counter(0, ctxt, counter, source)

    # (yjiang5) To support counters like instance:m1.tiny,
    # which include variable part at the end starting with ':'.
    # Hope we will not add such counters in future.
    def _variable_counter_name(self, name):
        m = name.partition(':')
        if m[1] == ':':
            return m[1].join((m[0], '*'))
        else:
            return name

    def support_counter(self, counter_name):
        counter_name = self._variable_counter_name(counter_name)
        if ('!' + counter_name) in self.counters:
            return False
        if '*' in self.counters:
            return True
        elif self.counters[0][0] == '!':
            return not ('!' + counter_name) in self.counters
        else:
            return counter_name in self.counters

    def flush(self, ctxt, source):
        """Flush data after all counter have been injected to pipeline."""

        LOG.audit("Flush pipeline %s", self)
        for (i, transformer) in enumerate(self.transformers):
            for c in transformer.flush(ctxt, source):
                self._publish_counter(i + 1, ctxt, c, source)

    def get_interval(self):
        return self.interval


class PipelineManager(object):
    """Pipeline Manager

    Pipeline manager sets up pipelines according to config file

    Usually only one pipeline manager exists in the system.

    """

    def __init__(self, cfg, publisher_manager):
        """Create the pipeline manager"""
        self._setup_pipelines(cfg, publisher_manager)

    def _setup_pipelines(self, cfg, publisher_manager):
        """Setup the pipelines according to config.

        The top of the cfg is a list of pipeline definitions.

        Pipeline definition is an dictionary specifying the target counters,
        the tranformers involved, and the target publishers:
        {
            "name": pipeline_name
            "interval": interval_time
            "counters" :  ["counter_1", "counter_2"],
            "tranformers":[
                              {"name": "Transformer_1",
                               "parameters": {"p1": "value"}},

                               {"name": "Transformer_2",
                               "parameters": {"p1": "value"}},
                           ]
            "publishers": ["publisher_1", "publisher_2"]
        }

        Interval is how many seconds should the counters be injected to
        the pipeline.

        Valid counter format is '*', '!counter_name', or 'counter_name'.
        '*' is wildcard symbol means any counters; '!counter_name' means
        "counter_name" will be excluded; 'counter_name' means 'counter_name'
        will be included.

        The 'counter_name" is Counter namedtuple's name field. For counter
        names with variable like "instance:m1.tiny", it's "instance:*", as
        returned by get_counter_list().

        Valid counters definition is all "included counter names", all
        "excluded counter names", wildcard and "excluded counter names", or
        only wildcard.

        Transformer's name is plugin name in setup.py.

        Publisher's name is plugin name in setup.py

        """
        transformer_manager = TransformerExtensionManager()
        self.pipelines = [Pipeline(pipedef, publisher_manager,
                                   transformer_manager)
                          for pipedef in cfg]

    def pipelines_for_counter(self, counter_name):
        """Get all pipelines that support counter"""
        return [p for p in self.pipelines if p.support_counter(counter_name)]

    def publish_counter(self, ctxt, counter, source):
        """Publish counter through pipelines

        This is helpful to notification mechanism, so that they don't need
        to maintain the private mapping cache from counter to pipelines.

        For polling based data collector, they may need keep private
        mapping cache for different interval support.

        """
        # TODO(yjiang5) Utilize a cache
        for p in self.pipelines:
            if p.support_counter(counter.name):
                p.publish_counter(ctxt, counter, source)


def setup_pipeline(publisher_manager):
    """Setup pipeline manager according to yaml config file."""
    cfg_file = cfg.CONF.pipeline_cfg_file
    if not os.path.exists(cfg_file):
        cfg_file = cfg.CONF.find_file(cfg_file)

    LOG.debug("Pipeline config file: %s", cfg_file)

    with open(cfg_file) as fap:
        data = fap.read()

    pipeline_cfg = yaml.safe_load(data)
    LOG.info("Pipeline config: %s", pipeline_cfg)

    return PipelineManager(pipeline_cfg,
                           publisher_manager)
