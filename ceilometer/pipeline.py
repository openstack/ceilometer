#
# Copyright 2013 Intel Corp.
# Copyright 2014 Red Hat, Inc
#
# Authors: Yunhong Jiang <yunhong.jiang@intel.com>
#          Eoghan Glynn <eglynn@redhat.com>
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

import abc
import fnmatch
import os

from oslo_config import cfg
import oslo_messaging
from oslo_utils import timeutils
import six
import yaml

from ceilometer.event.storage import models
from ceilometer.i18n import _
from ceilometer.openstack.common import log
from ceilometer import publisher
from ceilometer.publisher import utils as publisher_utils
from ceilometer import sample as sample_util
from ceilometer import transformer as xformer


OPTS = [
    cfg.StrOpt('pipeline_cfg_file',
               default="pipeline.yaml",
               help="Configuration file for pipeline definition."
               ),
    cfg.StrOpt('event_pipeline_cfg_file',
               default="event_pipeline.yaml",
               help="Configuration file for event pipeline definition."
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


@six.add_metaclass(abc.ABCMeta)
class PipelineEndpoint(object):

    def __init__(self, context, pipeline):
        self.publish_context = PublishContext(context, [pipeline])

    @abc.abstractmethod
    def sample(self, ctxt, publisher_id, event_type, payload, metadata):
        pass


class SamplePipelineEndpoint(PipelineEndpoint):
    def sample(self, ctxt, publisher_id, event_type, payload, metadata):
        samples = [
            sample_util.Sample(name=s['counter_name'],
                               type=s['counter_type'],
                               unit=s['counter_unit'],
                               volume=s['counter_volume'],
                               user_id=s['user_id'],
                               project_id=s['project_id'],
                               resource_id=s['resource_id'],
                               timestamp=s['timestamp'],
                               resource_metadata=s['resource_metadata'],
                               source=s.get('source'))
            for s in payload if publisher_utils.verify_signature(
                s, cfg.CONF.publisher.telemetry_secret)
        ]
        with self.publish_context as p:
            p(samples)


class EventPipelineEndpoint(PipelineEndpoint):
    def sample(self, ctxt, publisher_id, event_type, payload, metadata):
        events = [
            models.Event(
                message_id=ev['message_id'],
                event_type=ev['event_type'],
                generated=timeutils.normalize_time(
                    timeutils.parse_isotime(ev['generated'])),
                traits=[models.Trait(name, dtype,
                                     models.Trait.convert_value(dtype, value))
                        for name, dtype, value in ev['traits']],
                raw=ev.get('raw', {}))
            for ev in payload if publisher_utils.verify_signature(
                ev, cfg.CONF.publisher.telemetry_secret)
        ]
        try:
            with self.publish_context as p:
                p(events)
        except Exception:
            if not cfg.CONF.notification.ack_on_event_error:
                return oslo_messaging.NotificationResult.REQUEUE
            raise
        return oslo_messaging.NotificationResult.HANDLED


class PublishContext(object):

    def __init__(self, context, pipelines=None):
        pipelines = pipelines or []
        self.pipelines = set(pipelines)
        self.context = context

    def add_pipelines(self, pipelines):
        self.pipelines.update(pipelines)

    def __enter__(self):
        def p(data):
            for p in self.pipelines:
                p.publish_data(self.context, data)
        return p

    def __exit__(self, exc_type, exc_value, traceback):
        for p in self.pipelines:
            p.flush(self.context)


class Source(object):
    """Represents a source of samples or events."""

    def __init__(self, cfg):
        self.cfg = cfg

        try:
            self.name = cfg['name']
            self.sinks = cfg.get('sinks')
        except KeyError as err:
            raise PipelineException(
                "Required field %s not specified" % err.args[0], cfg)

    def __str__(self):
        return self.name

    def check_sinks(self, sinks):
        if not self.sinks:
            raise PipelineException(
                "No sink defined in source %s" % self,
                self.cfg)
        for sink in self.sinks:
            if sink not in sinks:
                raise PipelineException(
                    "Dangling sink %s from source %s" % (sink, self),
                    self.cfg)

    def check_source_filtering(self, data, d_type):
        """Source data rules checking

        - At least one meaningful datapoint exist
        - Included type and excluded type can't co-exist on the same pipeline
        - Included type meter and wildcard can't co-exist at same pipeline
        """
        if not data:
            raise PipelineException('No %s specified' % d_type, self.cfg)

        if ([x for x in data if x[0] not in '!*'] and
           [x for x in data if x[0] == '!']):
            raise PipelineException(
                'Both included and excluded %s specified' % d_type,
                cfg)

        if '*' in data and [x for x in data if x[0] not in '!*']:
            raise PipelineException(
                'Included %s specified with wildcard' % d_type,
                self.cfg)

    @staticmethod
    def is_supported(dataset, data_name):
        # Support wildcard like storage.* and !disk.*
        # Start with negation, we consider that the order is deny, allow
        if any(fnmatch.fnmatch(data_name, datapoint[1:])
               for datapoint in dataset if datapoint[0] == '!'):
            return False

        if any(fnmatch.fnmatch(data_name, datapoint)
               for datapoint in dataset if datapoint[0] != '!'):
            return True

        # if we only have negation, we suppose the default is allow
        return all(datapoint.startswith('!') for datapoint in dataset)


class EventSource(Source):
    """Represents a source of events.

    In effect it is a set of notification handlers capturing events for a set
    of matching notifications.
    """

    def __init__(self, cfg):
        super(EventSource, self).__init__(cfg)
        try:
            self.events = cfg['events']
        except KeyError as err:
            raise PipelineException(
                "Required field %s not specified" % err.args[0], cfg)
        self.check_source_filtering(self.events, 'events')

    def support_event(self, event_name):
        return self.is_supported(self.events, event_name)


class SampleSource(Source):
    """Represents a source of samples.

    In effect it is a set of pollsters and/or notification handlers emitting
    samples for a set of matching meters. Each source encapsulates meter name
    matching, polling interval determination, optional resource enumeration or
    discovery, and mapping to one or more sinks for publication.
    """

    def __init__(self, cfg):
        super(SampleSource, self).__init__(cfg)
        try:
            try:
                self.interval = int(cfg['interval'])
            except ValueError:
                raise PipelineException("Invalid interval value", cfg)
            # Support 'counters' for backward compatibility
            self.meters = cfg.get('meters', cfg.get('counters'))
        except KeyError as err:
            raise PipelineException(
                "Required field %s not specified" % err.args[0], cfg)
        if self.interval <= 0:
            raise PipelineException("Interval value should > 0", cfg)

        self.resources = cfg.get('resources') or []
        if not isinstance(self.resources, list):
            raise PipelineException("Resources should be a list", cfg)

        self.discovery = cfg.get('discovery') or []
        if not isinstance(self.discovery, list):
            raise PipelineException("Discovery should be a list", cfg)
        self.check_source_filtering(self.meters, 'meters')

    def support_meter(self, meter_name):
        return self.is_supported(self.meters, meter_name)


class Sink(object):
    """Represents a sink for the transformation and publication of data.

    Each sink config is concerned *only* with the transformation rules
    and publication conduits for data.

    In effect, a sink describes a chain of handlers. The chain starts
    with zero or more transformers and ends with one or more publishers.

    The first transformer in the chain is passed data from the
    corresponding source, takes some action such as deriving rate of
    change, performing unit conversion, or aggregating, before passing
    the modified data to next step.

    The subsequent transformers, if any, handle the data similarly.

    At the end of the chain, publishers publish the data. The exact
    publishing method depends on publisher type, for example, pushing
    into data storage via the message bus providing guaranteed delivery,
    or for loss-tolerant data UDP may be used.

    If no transformers are included in the chain, the publishers are
    passed data directly from the sink which are published unchanged.
    """

    def __init__(self, cfg, transformer_manager):
        self.cfg = cfg

        try:
            self.name = cfg['name']
            # It's legal to have no transformer specified
            self.transformer_cfg = cfg.get('transformers') or []
        except KeyError as err:
            raise PipelineException(
                "Required field %s not specified" % err.args[0], cfg)

        if not cfg.get('publishers'):
            raise PipelineException("No publisher specified", cfg)

        self.publishers = []
        for p in cfg['publishers']:
            if '://' not in p:
                # Support old format without URL
                p = p + "://"
            try:
                self.publishers.append(publisher.get_publisher(p,
                                                               self.NAMESPACE))
            except Exception:
                LOG.exception(_("Unable to load publisher %s"), p)

        self.transformers = self._setup_transformers(cfg, transformer_manager)

    def __str__(self):
        return self.name

    def _setup_transformers(self, cfg, transformer_manager):
        transformers = []
        for transformer in self.transformer_cfg:
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


class EventSink(Sink):

    NAMESPACE = 'ceilometer.event.publisher'

    def publish_events(self, ctxt, events):
        if events:
            for p in self.publishers:
                try:
                    p.publish_events(ctxt, events)
                except Exception:
                    LOG.exception(_(
                        "Pipeline %(pipeline)s: Continue after error "
                        "from publisher %(pub)s") % ({'pipeline': self,
                                                      'pub': p}))

    def flush(self, ctxt):
        """Flush data after all events have been injected to pipeline."""
        pass


class SampleSink(Sink):

    NAMESPACE = 'ceilometer.publisher'

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
            # TODO(gordc): only use one log level.
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
        if not self.transformers:
            transformed_samples = samples
        else:
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
            for p in self.publishers:
                try:
                    p.publish_samples(ctxt, transformed_samples)
                except Exception:
                    LOG.exception(_(
                        "Pipeline %(pipeline)s: Continue after error "
                        "from publisher %(pub)s") % ({'pipeline': self,
                                                      'pub': p}))

    def publish_samples(self, ctxt, samples):
        self._publish_samples(0, ctxt, samples)

    def flush(self, ctxt):
        """Flush data after all samples have been injected to pipeline."""

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


@six.add_metaclass(abc.ABCMeta)
class Pipeline(object):
    """Represents a coupling between a sink and a corresponding source."""

    def __init__(self, source, sink):
        self.source = source
        self.sink = sink
        self.name = str(self)

    def __str__(self):
        return (self.source.name if self.source.name == self.sink.name
                else '%s:%s' % (self.source.name, self.sink.name))

    def flush(self, ctxt):
        self.sink.flush(ctxt)

    @property
    def publishers(self):
        return self.sink.publishers

    @abc.abstractmethod
    def publish_data(self, ctxt, data):
        """Publish data from pipeline."""


class EventPipeline(Pipeline):
    """Represents a pipeline for Events."""

    def __str__(self):
        # NOTE(gordc): prepend a namespace so we ensure event and sample
        #              pipelines do not have the same name.
        return 'event:%s' % super(EventPipeline, self).__str__()

    def support_event(self, event_type):
        return self.source.support_event(event_type)

    def publish_data(self, ctxt, events):
        if not isinstance(events, list):
            events = [events]
        supported = [e for e in events
                     if self.source.support_event(e.event_type)]
        self.sink.publish_events(ctxt, supported)


class SamplePipeline(Pipeline):
    """Represents a pipeline for Samples."""

    def get_interval(self):
        return self.source.interval

    @property
    def resources(self):
        return self.source.resources

    @property
    def discovery(self):
        return self.source.discovery

    def support_meter(self, meter_name):
        return self.source.support_meter(meter_name)

    def publish_data(self, ctxt, samples):
        if not isinstance(samples, list):
            samples = [samples]
        supported = [s for s in samples if self.source.support_meter(s.name)]
        self.sink.publish_samples(ctxt, supported)


SAMPLE_TYPE = {'pipeline': SamplePipeline,
               'source': SampleSource,
               'sink': SampleSink}

EVENT_TYPE = {'pipeline': EventPipeline,
              'source': EventSource,
              'sink': EventSink}


class PipelineManager(object):
    """Pipeline Manager

    Pipeline manager sets up pipelines according to config file

    Usually only one pipeline manager exists in the system.

    """

    def __init__(self, cfg, transformer_manager, p_type=SAMPLE_TYPE):
        """Setup the pipelines according to config.

        The configuration is supported in one of two forms:

        1. Deprecated: the source and sink configuration are conflated
           as a list of consolidated pipelines.

           The pipelines are defined as a list of dictionaries each
           specifying the target samples, the transformers involved,
           and the target publishers, for example:

           [{"name": pipeline_1,
             "interval": interval_time,
             "meters" : ["meter_1", "meter_2"],
             "resources": ["resource_uri1", "resource_uri2"],
             "transformers": [
                              {"name": "Transformer_1",
                               "parameters": {"p1": "value"}},

                              {"name": "Transformer_2",
                               "parameters": {"p1": "value"}},
                              ],
             "publishers": ["publisher_1", "publisher_2"]
            },
            {"name": pipeline_2,
             "interval": interval_time,
             "meters" : ["meter_3"],
             "publishers": ["publisher_3"]
            },
           ]

        2. Decoupled: the source and sink configuration are separately
           specified before being linked together. This allows source-
           specific configuration, such as resource discovery, to be
           kept focused only on the fine-grained source while avoiding
           the necessity for wide duplication of sink-related config.

           The configuration is provided in the form of separate lists
           of dictionaries defining sources and sinks, for example:

           {"sources": [{"name": source_1,
                         "interval": interval_time,
                         "meters" : ["meter_1", "meter_2"],
                         "resources": ["resource_uri1", "resource_uri2"],
                         "sinks" : ["sink_1", "sink_2"]
                        },
                        {"name": source_2,
                         "interval": interval_time,
                         "meters" : ["meter_3"],
                         "sinks" : ["sink_2"]
                        },
                       ],
            "sinks": [{"name": sink_1,
                       "transformers": [
                              {"name": "Transformer_1",
                               "parameters": {"p1": "value"}},

                              {"name": "Transformer_2",
                               "parameters": {"p1": "value"}},
                             ],
                        "publishers": ["publisher_1", "publisher_2"]
                       },
                       {"name": sink_2,
                        "publishers": ["publisher_3"]
                       },
                      ]
           }

        The semantics of the common individual configuration elements
        are identical in the deprecated and decoupled version.

        The interval determines the cadence of sample injection into
        the pipeline where samples are produced under the direct control
        of an agent, i.e. via a polling cycle as opposed to incoming
        notifications.

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

        Transformer's name is plugin name in setup.cfg.

        Publisher's name is plugin name in setup.cfg

        """
        self.pipelines = []
        if 'sources' in cfg or 'sinks' in cfg:
            if not ('sources' in cfg and 'sinks' in cfg):
                raise PipelineException("Both sources & sinks are required",
                                        cfg)
            LOG.info(_('detected decoupled pipeline config format'))
            sources = [p_type['source'](s) for s in cfg.get('sources', [])]
            sinks = {}
            for s in cfg.get('sinks', []):
                if s['name'] in sinks:
                    raise PipelineException("Duplicated sink names: %s" %
                                            s['name'], self)
                else:
                    sinks[s['name']] = p_type['sink'](s, transformer_manager)
            for source in sources:
                source.check_sinks(sinks)
                for target in source.sinks:
                    pipe = p_type['pipeline'](source, sinks[target])
                    if pipe.name in [p.name for p in self.pipelines]:
                        raise PipelineException(
                            "Duplicate pipeline name: %s. Ensure pipeline"
                            " names are unique. (name is the source and sink"
                            " names combined)" % pipe.name, cfg)
                    else:
                        self.pipelines.append(pipe)
        else:
            LOG.warning(_('detected deprecated pipeline config format'))
            for pipedef in cfg:
                source = p_type['source'](pipedef)
                sink = p_type['sink'](pipedef, transformer_manager)
                pipe = p_type['pipeline'](source, sink)
                if pipe.name in [p.name for p in self.pipelines]:
                    raise PipelineException(
                        "Duplicate pipeline name: %s. Ensure pipeline"
                        " names are unique" % pipe.name, cfg)
                else:
                    self.pipelines.append(pipe)

    def publisher(self, context):
        """Build a new Publisher for these manager pipelines.

        :param context: The context.
        """
        return PublishContext(context, self.pipelines)


def _setup_pipeline_manager(cfg_file, transformer_manager, p_type=SAMPLE_TYPE):
    if not os.path.exists(cfg_file):
        cfg_file = cfg.CONF.find_file(cfg_file)

    LOG.debug(_("Pipeline config file: %s"), cfg_file)

    with open(cfg_file) as fap:
        data = fap.read()

    pipeline_cfg = yaml.safe_load(data)
    LOG.info(_("Pipeline config: %s"), pipeline_cfg)

    return PipelineManager(pipeline_cfg,
                           transformer_manager or
                           xformer.TransformerExtensionManager(
                               'ceilometer.transformer',
                           ), p_type)


def setup_event_pipeline(transformer_manager=None):
    """Setup event pipeline manager according to yaml config file."""
    cfg_file = cfg.CONF.event_pipeline_cfg_file
    return _setup_pipeline_manager(cfg_file, transformer_manager, EVENT_TYPE)


def setup_pipeline(transformer_manager=None):
    """Setup pipeline manager according to yaml config file."""
    cfg_file = cfg.CONF.pipeline_cfg_file
    return _setup_pipeline_manager(cfg_file, transformer_manager)
