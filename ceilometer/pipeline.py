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

import fnmatch
import itertools
import operator
import os

from oslo.config import cfg
import yaml

from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer import publisher


OPTS = [
    cfg.StrOpt('pipeline_cfg_file',
               default="pipeline.yaml",
               help="Configuration file for pipeline definition."
               ),
]

cfg.CONF.register_opts(OPTS)

LOG = log.getLogger(__name__)


class PipelineException(Exception):
    def __init__(self, message, pipeline_cfg):
        self.msg = message
        self.pipeline_cfg = pipeline_cfg

    def __str__(self):
        return 'Pipeline %s: %s' % (self.pipeline_cfg, self.msg)


class PublishContext(object):

    def __init__(self, context, pipelines=[]):
        self.pipelines = set(pipelines)
        self.context = context

    def add_pipelines(self, pipelines):
        self.pipelines.update(pipelines)

    def __enter__(self):
        def p(samples):
            for p in self.pipelines:
                p.publish_samples(self.context,
                                  samples)
        return p

    def __exit__(self, exc_type, exc_value, traceback):
        for p in self.pipelines:
            p.flush(self.context)


class Pipeline(object):
    """Sample handling pipeline

    Pipeline describes a chain of handlers. The chain starts with
    tranformer and ends with one or more publishers.

    The first transformer in the chain gets sample from data collector, i.e.
    pollster or notification handler, takes some action like dropping,
    aggregation, changing field etc, then passes the updated sample
    to next step.

    The subsequent transformers, if any, handle the data similarly.

    In the end of the chain, publishers publish the data. The exact publishing
    method depends on publisher type, for example, pushing into data storage
    through message bus, sending to external CW software through CW API call.

    If no transformer is included in the chain, the publishers get samples
    from data collector and publish them directly.

    """

    def __init__(self, cfg, transformer_manager):
        self.cfg = cfg

        try:
            self.name = cfg['name']
            try:
                self.interval = int(cfg['interval'])
            except ValueError:
                raise PipelineException("Invalid interval value", cfg)
            # Support 'counters' for backward compatibility
            self.meters = cfg.get('meters', cfg.get('counters'))
            # It's legal to have no transformer specified
            self.transformer_cfg = cfg['transformers'] or []
        except KeyError as err:
            raise PipelineException(
                "Required field %s not specified" % err.args[0], cfg)

        if self.interval <= 0:
            raise PipelineException("Interval value should > 0", cfg)

        self._check_meters()

        if not cfg.get('publishers'):
            raise PipelineException("No publisher specified", cfg)

        self.publishers = []
        for p in cfg['publishers']:
            if '://' not in p:
                # Support old format without URL
                p = p + "://"
            try:
                self.publishers.append(publisher.get_publisher(p))
            except Exception:
                LOG.exception(_("Unable to load publisher %s"), p)

        self.transformers = self._setup_transformers(cfg, transformer_manager)

        self.resources = cfg.get('resources') or []
        if not isinstance(self.resources, list):
            raise PipelineException("Resources should be a list", cfg)

    def __str__(self):
        return self.name

    def _check_meters(self):
        """Meter rules checking

        At least one meaningful meter exist
        Included type and excluded type meter can't co-exist at
        the same pipeline
        Included type meter and wildcard can't co-exist at same pipeline

        """
        meters = self.meters
        if not meters:
            raise PipelineException("No meter specified", self.cfg)

        if [x for x in meters if x[0] not in '!*'] and \
           [x for x in meters if x[0] == '!']:
            raise PipelineException(
                "Both included and excluded meters specified",
                cfg)

        if '*' in meters and [x for x in meters if x[0] not in '!*']:
            raise PipelineException(
                "Included meters specified with wildcard",
                self.cfg)

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
            LOG.info(_(
                "Pipeline %(pipeline)s: Setup transformer instance %(name)s "
                "with parameter %(param)s") % ({'pipeline': self,
                                                'name': transformer['name'],
                                                'param': parameter}))

        return transformers

    def _transform_sample(self, start, ctxt, sample):
        try:
            for transformer in self.transformers[start:]:
                sample = transformer.handle_sample(ctxt, sample)
                if not sample:
                    LOG.debug(_(
                        "Pipeline %(pipeline)s: Sample dropped by "
                        "transformer %(trans)s") % ({'pipeline': self,
                                                     'trans': transformer}))
                    return
            return sample
        except Exception as err:
            LOG.warning(_("Pipeline %(pipeline)s: "
                          "Exit after error from transformer "
                          "%(trans)s for %(smp)s") % ({'pipeline': self,
                                                       'trans': transformer,
                                                       'smp': sample}))
            LOG.exception(err)

    def _publish_samples(self, start, ctxt, samples):
        """Push samples into pipeline for publishing.

        :param start: The first transformer that the sample will be injected.
                      This is mainly for flush() invocation that transformer
                      may emit samples.
        :param ctxt: Execution context from the manager or service.
        :param samples: Sample list.

        """

        transformed_samples = []
        for sample in samples:
            LOG.debug(_(
                "Pipeline %(pipeline)s: Transform sample "
                "%(smp)s from %(trans)s transformer") % ({'pipeline': self,
                                                          'smp': sample,
                                                          'trans': start}))
            sample = self._transform_sample(start, ctxt, sample)
            if sample:
                transformed_samples.append(sample)

        if transformed_samples:
            LOG.audit(_("Pipeline %s: Publishing samples"), self)
            for p in self.publishers:
                try:
                    p.publish_samples(ctxt, transformed_samples)
                except Exception:
                    LOG.exception(_(
                        "Pipeline %(pipeline)s: Continue after error "
                        "from publisher %(pub)s") % ({'pipeline': self,
                                                      'pub': p}))
            LOG.audit(_("Pipeline %s: Published samples") % self)

    def publish_sample(self, ctxt, sample):
        self.publish_samples(ctxt, [sample])

    def publish_samples(self, ctxt, samples):
        for meter_name, samples in itertools.groupby(
                sorted(samples, key=operator.attrgetter('name')),
                operator.attrgetter('name')):
            if self.support_meter(meter_name):
                self._publish_samples(0, ctxt, samples)

    # (yjiang5) To support meters like instance:m1.tiny,
    # which include variable part at the end starting with ':'.
    # Hope we will not add such meters in future.
    def _variable_meter_name(self, name):
        m = name.partition(':')
        if m[1] == ':':
            return m[1].join((m[0], '*'))
        else:
            return name

    def support_meter(self, meter_name):
        meter_name = self._variable_meter_name(meter_name)

        # Special case: if we only have negation, we suppose the default it
        # allow
        if all(meter.startswith('!') for meter in self.meters):
            default = True
        else:
            default = False

        # Support wildcard like storage.* and !disk.*
        # Start with negation, we consider that the order is deny, allow
        if any(fnmatch.fnmatch(meter_name, meter[1:])
               for meter in self.meters
               if meter[0] == '!'):
            return False

        if any(fnmatch.fnmatch(meter_name, meter)
               for meter in self.meters
               if meter[0] != '!'):
            return True

        return default

    def flush(self, ctxt):
        """Flush data after all samples have been injected to pipeline."""

        LOG.audit(_("Flush pipeline %s"), self)
        for (i, transformer) in enumerate(self.transformers):
            try:
                self._publish_samples(i + 1, ctxt,
                                      list(transformer.flush(ctxt)))
            except Exception as err:
                LOG.warning(_(
                    "Pipeline %(pipeline)s: Error flushing "
                    "transformer %(trans)s") % ({'pipeline': self,
                                                 'trans': transformer}))
                LOG.exception(err)

    def get_interval(self):
        return self.interval


class PipelineManager(object):
    """Pipeline Manager

    Pipeline manager sets up pipelines according to config file

    Usually only one pipeline manager exists in the system.

    """

    def __init__(self, cfg,
                 transformer_manager):
        """Setup the pipelines according to config.

        The top of the cfg is a list of pipeline definitions.

        Pipeline definition is an dictionary specifying the target samples,
        the tranformers involved, and the target publishers:
        {
            "name": pipeline_name
            "interval": interval_time
            "meters" :  ["meter_1", "meter_2"],
            "resources": ["resource_uri1", "resource_uri2"],
            "tranformers":[
                              {"name": "Transformer_1",
                               "parameters": {"p1": "value"}},

                               {"name": "Transformer_2",
                               "parameters": {"p1": "value"}},
                           ]
            "publishers": ["publisher_1", "publisher_2"]
        }

        Interval is how many seconds should the samples be injected to
        the pipeline.

        Valid meter format is '*', '!meter_name', or 'meter_name'.
        '*' is wildcard symbol means any meters; '!meter_name' means
        "meter_name" will be excluded; 'meter_name' means 'meter_name'
        will be included.

        The 'meter_name" is Sample name field. For meter names with
        variable like "instance:m1.tiny", it's "instance:*".

        Valid meters definition is all "included meter names", all
        "excluded meter names", wildcard and "excluded meter names", or
        only wildcard.

        The resources is list of URI indicating the resources from where
        the meters should be polled. It's optional and it's up to the
        specific pollster to decide how to use it.

        Transformer's name is plugin name in setup.py.

        Publisher's name is plugin name in setup.py

        """
        self.pipelines = [Pipeline(pipedef, transformer_manager)
                          for pipedef in cfg]

    def publisher(self, context):
        """Build a new Publisher for these manager pipelines.

        :param context: The context.
        """
        return PublishContext(context, self.pipelines)


def setup_pipeline(transformer_manager):
    """Setup pipeline manager according to yaml config file."""
    cfg_file = cfg.CONF.pipeline_cfg_file
    if not os.path.exists(cfg_file):
        cfg_file = cfg.CONF.find_file(cfg_file)

    LOG.debug(_("Pipeline config file: %s"), cfg_file)

    with open(cfg_file) as fap:
        data = fap.read()

    pipeline_cfg = yaml.safe_load(data)
    LOG.info(_("Pipeline config: %s"), pipeline_cfg)

    return PipelineManager(pipeline_cfg,
                           transformer_manager)
