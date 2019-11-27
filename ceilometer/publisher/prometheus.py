#
# Copyright 2016 IBM
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

from ceilometer.publisher import http
from ceilometer import sample


class PrometheusPublisher(http.HttpPublisher):
    """Publish metering data to Prometheus Pushgateway endpoint

    This dispatcher inherits from all options of the http dispatcher.

    To use this publisher for samples, add the following section to the
    /etc/ceilometer/pipeline.yaml file or simply add it to an existing
    pipeline::

          - name: meter_file
            meters:
                - "*"
            publishers:
                - prometheus://mypushgateway/metrics/job/ceilometer

    """

    HEADERS = {'Content-type': 'plain/text'}

    def publish_samples(self, samples):
        """Send a metering message for publishing

        :param samples: Samples from pipeline after transformation
        """
        if not samples:
            return

        data = ""
        doc_done = set()
        for s in samples:
            # NOTE(sileht): delta can't be converted into prometheus data
            # format so don't set the metric type for it
            metric_type = None
            if s.type == sample.TYPE_CUMULATIVE:
                metric_type = "counter"
            elif s.type == sample.TYPE_GAUGE:
                metric_type = "gauge"

            curated_sname = s.name.replace(".", "_")

            if metric_type and curated_sname not in doc_done:
                data += "# TYPE %s %s\n" % (curated_sname, metric_type)
                doc_done.add(curated_sname)

            # NOTE(sileht): prometheus pushgateway doesn't allow to push
            # timestamp_ms
            #
            # timestamp_ms = (
            #     s.get_iso_timestamp().replace(tzinfo=None) -
            #     datetime.utcfromtimestamp(0)
            # ).total_seconds() * 1000
            # data += '%s{resource_id="%s"} %s %d\n' % (
            #     curated_sname, s.resource_id, s.volume, timestamp_ms)

            data += '%s{resource_id="%s", project_id="%s"} %s\n' % (
                curated_sname, s.resource_id, s.project_id, s.volume)
        self._do_post(data)

    @staticmethod
    def publish_events(events):
        raise NotImplementedError
