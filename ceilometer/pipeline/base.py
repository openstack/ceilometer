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
from ceilometer import publisher

OPTS = [
    cfg.StrOpt('pipeline_cfg_file',
               default="pipeline.yaml",
               help="Configuration file for pipeline definition."
               ),
    cfg.StrOpt('event_pipeline_cfg_file',
               default="event_pipeline.yaml",
               deprecated_for_removal=True,
               help="Configuration file for event pipeline definition."
               ),
]


LOG = log.getLogger(__name__)


class PipelineException(agent.ConfigException):
    def __init__(self, message, cfg):
        super(PipelineException, self).__init__('Pipeline', message, cfg)


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

    In effect, a sink describes a chain of handlers. The chain ends with one or
    more publishers.

    At the end of the chain, publishers publish the data. The exact
    publishing method depends on publisher type, for example, pushing
    into data storage via the message bus providing guaranteed delivery,
    or for loss-tolerant data UDP may be used.

    """

    def __init__(self, conf, cfg, publisher_manager):
        self.conf = conf
        self.cfg = cfg

        try:
            self.name = cfg['name']
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

    def __str__(self):
        return self.name

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

    @abc.abstractmethod
    def supported(self, data):
        """Attribute to filter on. Pass if no partitioning."""


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

    def __init__(self, conf, cfg_file):
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

        Publisher's name is plugin name in setup.cfg

        """
        super(PipelineManager, self).__init__(conf)
        cfg = self.load_config(cfg_file)
        self.pipelines = []
        if not ('sources' in cfg and 'sinks' in cfg):
            raise PipelineException("Both sources & sinks are required",
                                    cfg)
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

    def get_main_endpoints(self):
        """Return endpoints for main queue."""
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

    audit = _consume_and_drop
    critical = _consume_and_drop
    debug = _consume_and_drop
    error = _consume_and_drop
    info = _consume_and_drop
    sample = _consume_and_drop
    warn = _consume_and_drop
