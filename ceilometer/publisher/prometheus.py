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

from oslo_log import log
from urllib import parse as urlparse

from ceilometer.publisher import http
from ceilometer import sample

LOG = log.getLogger(__name__)


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

    Notes about grouping labels:
    - Prometheus Pushgateway groups metrics by a set of grouping labels that
      appear in the URL path after the job segment.
    - Without grouping labels, pushing a metric family again will replace all
      time series of that metric name within the group. To avoid overrides when
      multiple pushes contain the same metric name with different label sets,
      this publisher, if no grouping labels are configured in the URL, will
      push per resource (using `resource_id` as grouping label in the path).
    - If grouping labels are already present in the path, they are preserved,
      and a single push is performed, leaving grouping control to the operator.

    """

    HEADERS = {'Content-type': 'plain/text'}

    def __init__(self, conf, parsed_url):
        path = parsed_url.path or ''
        self._has_grouping = False
        if path.startswith('/metrics/job/'):
            segments = [seg for seg in path.split('/') if seg]
            # segments: ['metrics', 'job', '<job>', <optional grouping...>]
            self._has_grouping = len(segments) > 3
        super().__init__(conf, parsed_url)

    @staticmethod
    def _sample_to_text(s, doc_done):
        # NOTE(sileht): delta can't be converted into prometheus data
        # format so don't set the metric type for it
        metric_type = None
        if s.type == sample.TYPE_CUMULATIVE:
            metric_type = "counter"
        elif s.type == sample.TYPE_GAUGE:
            metric_type = "gauge"
        curated_sname = s.name.replace(".", "_").replace("-", "_")
        lines = []
        if metric_type and curated_sname not in doc_done:
            lines.append(f"# TYPE {curated_sname} {metric_type}\n")
            doc_done.add(curated_sname)
        lines.append('%s{resource_id="%s", user_id="%s", project_id="%s"}'
                     ' %s\n' % (curated_sname, s.resource_id, s.user_id,
                                s.project_id, s.volume))
        return "".join(lines)

    def publish_samples(self, samples):
        """Send a metering message for publishing

        :param samples: Samples from pipeline after transformation
        """
        if not samples:
            return

        if self._has_grouping:
            doc_done = set()
            data = "".join(self._sample_to_text(s, doc_done) for s in samples)
            self._do_post(data)
            return

        payloads = {}
        doc_done_by_res = {}
        for s in samples:
            rid = s.resource_id
            if rid not in payloads:
                payloads[rid] = []
                doc_done_by_res[rid] = set()
            payloads[rid].append(self._sample_to_text(s, doc_done_by_res[rid]))

        for rid, chunks in payloads.items():
            rid_q = urlparse.quote(str(rid), safe='')
            self._do_post("".join(chunks),
                          sub_path='/resource_id/' + rid_q)

    @staticmethod
    def publish_events(events):
        raise NotImplementedError
