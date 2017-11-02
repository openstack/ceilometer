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
from oslo_log import log
from stevedore import extension

from ceilometer import agent
from ceilometer import pipeline

LOG = log.getLogger(__name__)


class SampleEndpoint(pipeline.NotificationEndpoint):

    def info(self, notifications):
        """Convert message at info level to Ceilometer sample.

        :param notifications: list of notifications
        """
        return self.process_notifications('info', notifications)

    def sample(self, notifications):
        """Convert message at sample level to Ceilometer Event.

        :param notifications: list of notifications
        """
        return self.process_notifications('sample', notifications)

    def process_notifications(self, priority, notifications):
        for message in notifications:
            try:
                with self.manager.publisher() as p:
                    p(list(self.build_sample(message)))
            except Exception:
                LOG.error('Fail to process notification', exc_info=True)

    def build_sample(notification):
        """Build sample from provided notification."""
        pass


class SampleSource(pipeline.PipelineSource):
    """Represents a source of samples.

    In effect it is a set of notification handlers processing
    samples for a set of matching meters. Each source encapsulates meter name
    matching and mapping to one or more sinks for publication.
    """

    def __init__(self, cfg):
        super(SampleSource, self).__init__(cfg)
        try:
            self.meters = cfg['meters']
        except KeyError:
            raise pipeline.PipelineException("Missing meters value", cfg)
        try:
            self.check_source_filtering(self.meters, 'meters')
        except agent.SourceException as err:
            raise pipeline.PipelineException(err.msg, cfg)

    def support_meter(self, meter_name):
        return self.is_supported(self.meters, meter_name)


class SampleSink(pipeline.Sink):

    def _transform_sample(self, start, sample):
        try:
            for transformer in self.transformers[start:]:
                sample = transformer.handle_sample(sample)
                if not sample:
                    LOG.debug(
                        "Pipeline %(pipeline)s: Sample dropped by "
                        "transformer %(trans)s", {'pipeline': self,
                                                  'trans': transformer})
                    return
            return sample
        except Exception:
            LOG.error("Pipeline %(pipeline)s: Exit after error "
                      "from transformer %(trans)s "
                      "for %(smp)s" % {'pipeline': self,
                                       'trans': transformer,
                                       'smp': sample},
                      exc_info=True)

    def _publish_samples(self, start, samples):
        """Push samples into pipeline for publishing.

        :param start: The first transformer that the sample will be injected.
                      This is mainly for flush() invocation that transformer
                      may emit samples.
        :param samples: Sample list.

        """

        transformed_samples = []
        if not self.transformers:
            transformed_samples = samples
        else:
            for sample in samples:
                LOG.debug(
                    "Pipeline %(pipeline)s: Transform sample "
                    "%(smp)s from %(trans)s transformer", {'pipeline': self,
                                                           'smp': sample,
                                                           'trans': start})
                sample = self._transform_sample(start, sample)
                if sample:
                    transformed_samples.append(sample)

        if transformed_samples:
            for p in self.publishers:
                try:
                    p.publish_samples(transformed_samples)
                except Exception:
                    LOG.error("Pipeline %(pipeline)s: Continue after "
                              "error from publisher %(pub)s"
                              % {'pipeline': self, 'pub': p},
                              exc_info=True)

    def publish_samples(self, samples):
        self._publish_samples(0, samples)

    def flush(self):
        """Flush data after all samples have been injected to pipeline."""

        for (i, transformer) in enumerate(self.transformers):
            try:
                self._publish_samples(i + 1,
                                      list(transformer.flush()))
            except Exception:
                LOG.error("Pipeline %(pipeline)s: Error "
                          "flushing transformer %(trans)s"
                          % {'pipeline': self, 'trans': transformer},
                          exc_info=True)


class SamplePipeline(pipeline.Pipeline):
    """Represents a pipeline for Samples."""

    def support_meter(self, meter_name):
        return self.source.support_meter(meter_name)

    def _validate_volume(self, s):
        volume = s.volume
        if volume is None:
            LOG.warning(
                'metering data %(counter_name)s for %(resource_id)s '
                '@ %(timestamp)s has no volume (volume: None), the sample will'
                ' be dropped'
                % {'counter_name': s.name,
                   'resource_id': s.resource_id,
                   'timestamp': s.timestamp if s.timestamp else 'NO TIMESTAMP'}
            )
            return False
        if not isinstance(volume, (int, float)):
            try:
                volume = float(volume)
            except ValueError:
                LOG.warning(
                    'metering data %(counter_name)s for %(resource_id)s '
                    '@ %(timestamp)s has volume which is not a number '
                    '(volume: %(counter_volume)s), the sample will be dropped'
                    % {'counter_name': s.name,
                       'resource_id': s.resource_id,
                       'timestamp': (
                           s.timestamp if s.timestamp else 'NO TIMESTAMP'),
                       'counter_volume': volume}
                )
                return False
        return True

    def publish_data(self, samples):
        if not isinstance(samples, list):
            samples = [samples]
        supported = [s for s in samples if self.source.support_meter(s.name)
                     and self._validate_volume(s)]
        self.sink.publish_samples(supported)


class SamplePipelineManager(pipeline.PipelineManager):

    def __init__(self, conf):
        # FIXME(gordc): improve how we set pipeline specific models
        pipeline_types = {'name': 'sample', 'pipeline': SamplePipeline,
                          'source': SampleSource, 'sink': SampleSink}
        super(SamplePipelineManager, self).__init__(
            conf, conf.pipeline_cfg_file, self.get_transform_manager(),
            pipeline_types)

    @staticmethod
    def get_transform_manager():
        return extension.ExtensionManager('ceilometer.transformer')
