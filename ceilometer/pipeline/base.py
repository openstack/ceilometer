#
# Copyright 2013 Intel Corp.
# Copyright 2014 Red Hat, Inc
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

from oslo_config import cfg
from oslo_log import log
import oslo_messaging
import six

from ceilometer import agent
from ceilometer import messaging
from ceilometer import publisher

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


LOG = log.getLogger(__name__)


class PipelineException(agent.ConfigException):
    def __init__(self, message, cfg):
        super(PipelineException, self).__init__('Pipeline', message, cfg)


class InterimPublishContext(object):
    """Publisher to hash/shard data to pipelines"""

    def __init__(self, conf, mgr):
        self.conf = conf
        self.mgr = mgr
        self.notifiers = self._get_notifiers(messaging.get_transport(conf))

    def _get_notifiers(self, transport):
        notifiers = []
        for x in range(self.conf.notification.pipeline_processing_queues):
            notifiers.append(oslo_messaging.Notifier(
                transport,
                driver=self.conf.publisher_notifier.telemetry_driver,
                topics=['-'.join(
                    [self.mgr.NOTIFICATION_IPC, self.mgr.pm_type, str(x)])]))
        return notifiers

    @staticmethod
    def hash_grouping(datapoint, grouping_keys):
        # FIXME(gordc): this logic only supports a single grouping_key. we
        # need to change to support pipeline with multiple transformers and
        # different grouping_keys
        value = ''
        for key in grouping_keys or []:
            value += datapoint.get(key) if datapoint.get(key) else ''
        return hash(value)

    def __enter__(self):
        def p(data):
            data = [data] if not isinstance(data, list) else data
            for datapoint in data:
                for pipe in self.mgr.pipelines:
                    if pipe.supported(datapoint):
                        serialized_data = pipe.serializer(datapoint)
                        key = (self.hash_grouping(serialized_data,
                                                  pipe.get_grouping_key())
                               % len(self.notifiers))
                        self.notifiers[key].sample({}, event_type=pipe.name,
                                                   payload=[serialized_data])
        return p

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class PublishContext(object):
    def __init__(self, pipelines):
        self.pipelines = pipelines or []

    def __enter__(self):
        def p(data):
            for p in self.pipelines:
                p.publish_data(data)
        return p

    def __exit__(self, exc_type, exc_value, traceback):
        for p in self.pipelines:
            p.flush()


class PipelineSource(agent.Source):
    """Represents a source of samples or events."""

    def __init__(self, cfg):
        try:
            super(PipelineSource, self).__init__(cfg)
        except agent.SourceException as err:
            raise PipelineException(err.msg, cfg)
        try:
            self.sinks = cfg['sinks']
        except KeyError as err:
            raise PipelineException(
                "Required field %s not specified" % err.args[0], cfg)

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

    def __init__(self, conf, cfg, transformer_manager, publisher_manager):
        self.conf = conf
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
                self.publishers.append(publisher_manager.get(p))
            except Exception:
                LOG.error("Unable to load publisher %s", p,
                          exc_info=True)

        self.multi_publish = True if len(self.publishers) > 1 else False
        self.transformers = self._setup_transformers(cfg, transformer_manager)

    def __str__(self):
        return self.name

    def _setup_transformers(self, cfg, transformer_manager):
        transformers = []
        for transformer in self.transformer_cfg:
            parameter = transformer['parameters'] or {}
            try:
                ext = transformer_manager[transformer['name']]
            except KeyError:
                raise PipelineException(
                    "No transformer named %s loaded" % transformer['name'],
                    cfg)
            transformers.append(ext.plugin(**parameter))
            LOG.info(
                "Pipeline %(pipeline)s: Setup transformer instance %(name)s "
                "with parameter %(param)s" % ({'pipeline': self,
                                               'name': transformer['name'],
                                               'param': parameter}))

        return transformers

    @staticmethod
    def flush():
        """Flush data after all events have been injected to pipeline."""


@six.add_metaclass(abc.ABCMeta)
class Pipeline(object):
    """Represents a coupling between a sink and a corresponding source."""

    def __init__(self, conf, source, sink):
        self.conf = conf
        self.source = source
        self.sink = sink
        self.name = str(self)

    def __str__(self):
        return (self.source.name if self.source.name == self.sink.name
                else '%s:%s' % (self.source.name, self.sink.name))

    def flush(self):
        self.sink.flush()

    @property
    def publishers(self):
        return self.sink.publishers

    @abc.abstractmethod
    def publish_data(self, data):
        """Publish data from pipeline."""

    @abc.abstractproperty
    def default_grouping_key(self):
        """Attribute to hash data on. Pass if no partitioning."""

    @abc.abstractmethod
    def supported(self, data):
        """Attribute to filter on. Pass if no partitioning."""

    @abc.abstractmethod
    def serializer(self, data):
        """Serialize data for interim transport. Pass if no partitioning."""

    def get_grouping_key(self):
        keys = []
        for transformer in self.sink.transformers:
            keys += transformer.grouping_keys
        return list(set(keys)) or self.default_grouping_key


class PublisherManager(object):
    def __init__(self, conf, purpose):
        self._loaded_publishers = {}
        self._conf = conf
        self._purpose = purpose

    def get(self, url):
        if url not in self._loaded_publishers:
            p = publisher.get_publisher(
                self._conf, url,
                'ceilometer.%s.publisher' % self._purpose)
            self._loaded_publishers[url] = p
        return self._loaded_publishers[url]


class PipelineManager(agent.ConfigManagerBase):
    """Pipeline Manager

    Pipeline manager sets up pipelines according to config file
    """

    NOTIFICATION_IPC = 'ceilometer_ipc'

    def __init__(self, conf, cfg_file, transformer_manager, partition):
        """Setup the pipelines according to config.

        The configuration is supported as follows:

        Decoupled: the source and sink configuration are separately
        specified before being linked together. This allows source-
        specific configuration, such as meter handling, to be
        kept focused only on the fine-grained source while avoiding
        the necessity for wide duplication of sink-related config.

        The configuration is provided in the form of separate lists
        of dictionaries defining sources and sinks, for example:

        {"sources": [{"name": source_1,
                      "meters" : ["meter_1", "meter_2"],
                      "sinks" : ["sink_1", "sink_2"]
                     },
                     {"name": source_2,
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

        Valid meter format is '*', '!meter_name', or 'meter_name'.
        '*' is wildcard symbol means any meters; '!meter_name' means
        "meter_name" will be excluded; 'meter_name' means 'meter_name'
        will be included.

        Valid meters definition is all "included meter names", all
        "excluded meter names", wildcard and "excluded meter names", or
        only wildcard.

        Transformer's name is plugin name in setup.cfg.

        Publisher's name is plugin name in setup.cfg

        """
        super(PipelineManager, self).__init__(conf)
        cfg = self.load_config(cfg_file)
        self.pipelines = []
        if not ('sources' in cfg and 'sinks' in cfg):
            raise PipelineException("Both sources & sinks are required",
                                    cfg)
        LOG.info('detected decoupled pipeline config format')
        publisher_manager = PublisherManager(self.conf, self.pm_type)

        unique_names = set()
        sources = []
        for s in cfg.get('sources'):
            name = s.get('name')
            if name in unique_names:
                raise PipelineException("Duplicated source names: %s" %
                                        name, self)
            else:
                unique_names.add(name)
                sources.append(self.pm_source(s))
        unique_names.clear()

        sinks = {}
        for s in cfg.get('sinks'):
            name = s.get('name')
            if name in unique_names:
                raise PipelineException("Duplicated sink names: %s" %
                                        name, self)
            else:
                unique_names.add(name)
                sinks[s['name']] = self.pm_sink(self.conf, s,
                                                transformer_manager,
                                                publisher_manager)
        unique_names.clear()

        for source in sources:
            source.check_sinks(sinks)
            for target in source.sinks:
                pipe = self.pm_pipeline(self.conf, source, sinks[target])
                if pipe.name in unique_names:
                    raise PipelineException(
                        "Duplicate pipeline name: %s. Ensure pipeline"
                        " names are unique. (name is the source and sink"
                        " names combined)" % pipe.name, cfg)
                else:
                    unique_names.add(pipe.name)
                    self.pipelines.append(pipe)
        unique_names.clear()
        self.partition = partition

    @abc.abstractproperty
    def pm_type(self):
        """Pipeline manager type."""

    @abc.abstractproperty
    def pm_pipeline(self):
        """Pipeline class"""

    @abc.abstractproperty
    def pm_source(self):
        """Pipeline source class"""

    @abc.abstractproperty
    def pm_sink(self):
        """Pipeline sink class"""

    def publisher(self):
        """Build publisher for pipeline publishing."""
        return PublishContext(self.pipelines)

    def interim_publisher(self):
        """Build publishing context for IPC."""
        return InterimPublishContext(self.conf, self)

    def get_main_publisher(self):
        """Return the publishing context to use"""
        return (self.interim_publisher() if self.partition else
                self.publisher())

    def get_main_endpoints(self):
        """Return endpoints for main queue."""
        pass

    def get_interim_endpoints(self):
        """Return endpoints for interim pipeline queues."""
        pass


class NotificationEndpoint(object):
    """Base Endpoint for plugins that support the notification API."""

    event_types = []
    """List of strings to filter messages on."""

    def __init__(self, conf, publisher):
        super(NotificationEndpoint, self).__init__()
        # NOTE(gordc): this is filter rule used by oslo.messaging to dispatch
        # messages to an endpoint.
        if self.event_types:
            self.filter_rule = oslo_messaging.NotificationFilter(
                event_type='|'.join(self.event_types))
        self.conf = conf
        self.publisher = publisher

    @abc.abstractmethod
    def process_notifications(self, priority, notifications):
        """Return a sequence of Counter instances for the given message.

        :param message: Message to process.
        """

    @classmethod
    def _consume_and_drop(cls, notifications):
        """RPC endpoint for useless notification level"""
        # NOTE(sileht): nothing special todo here, but because we listen
        # for the generic notification exchange we have to consume all its
        # queues


class MainNotificationEndpoint(NotificationEndpoint):
    """Listens to queues on all priority levels and clears by default."""

    audit = NotificationEndpoint._consume_and_drop
    critical = NotificationEndpoint._consume_and_drop
    debug = NotificationEndpoint._consume_and_drop
    error = NotificationEndpoint._consume_and_drop
    info = NotificationEndpoint._consume_and_drop
    sample = NotificationEndpoint._consume_and_drop
    warn = NotificationEndpoint._consume_and_drop
