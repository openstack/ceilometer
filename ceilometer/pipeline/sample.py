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
from ceilometer.pipeline import base

LOG = log.getLogger(__name__)


class SampleEndpoint(base.NotificationEndpoint):

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
                with self.publisher as p:
                    p(list(self.build_sample(message)))
            except Exception:
                LOG.error('Fail to process notification', exc_info=True)

    def build_sample(notification):
        """Build sample from provided notification."""
        pass


class SampleSource(base.PipelineSource):
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
            raise base.PipelineException("Missing meters value", cfg)
        try:
            self.check_source_filtering(self.meters, 'meters')
        except agent.SourceException as err:
            raise base.PipelineException(err.msg, cfg)

    def support_meter(self, meter_name):
        return self.is_supported(self.meters, meter_name)


class SampleSink(base.Sink):

    def publish_samples(self, samples):
        """Push samples into pipeline for publishing.

        :param samples: Sample list.
        """

        if samples:
            for p in self.publishers:
                try:
                    p.publish_samples(samples)
                except Exception:
                    LOG.error("Pipeline %(pipeline)s: Continue after "
                              "error from publisher %(pub)s"
                              % {'pipeline': self, 'pub': p},
                              exc_info=True)

    @staticmethod
    def flush():
        pass


class SamplePipeline(base.Pipeline):
    """Represents a pipeline for Samples."""

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
        supported = [s for s in samples if self.supported(s)
                     and self._validate_volume(s)]
        self.sink.publish_samples(supported)

    def supported(self, sample):
        return self.source.support_meter(sample.name)


class SamplePipelineManager(base.PipelineManager):

    pm_type = 'sample'
    pm_pipeline = SamplePipeline
    pm_source = SampleSource
    pm_sink = SampleSink

    def __init__(self, conf):
        super(SamplePipelineManager, self).__init__(
            conf, conf.pipeline_cfg_file)

    def get_main_endpoints(self):
        exts = extension.ExtensionManager(
            namespace='ceilometer.sample.endpoint',
            invoke_on_load=True,
            invoke_args=(self.conf, self.publisher()))
        return [ext.obj for ext in exts]
