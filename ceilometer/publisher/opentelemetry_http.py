#
# Copyright 2024 cmss, inc.
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

import json
import time

from oslo_log import log
from oslo_utils import timeutils

from ceilometer.publisher import http
from ceilometer import sample as smp

LOG = log.getLogger(__name__)


class OpentelemetryHttpPublisher(http.HttpPublisher):
    """Publish metering data to Opentelemetry Collector endpoint

    This dispatcher inherits from all options of the http dispatcher.

    To use this publisher for samples, add the following section to the
    /etc/ceilometer/pipeline.yaml file or simply add it to an existing
    pipeline::

          - name: meter_file
            meters:
                - "*"
            publishers:
                - opentelemetryhttp://opentelemetry-http-ip:4318/v1/metrics

    """

    HEADERS = {'Content-type': 'application/json'}

    @staticmethod
    def get_attribute_model(key, value):
        return {
            "key": key,
            "value": {
                "string_value": value
            }
        }

    def get_attributes_model(self, sample):
        attributes = []
        resource_id_attr = self.get_attribute_model("resource_id",
                                                    sample.resource_id)
        user_id_attr = self.get_attribute_model("user_id", sample.user_id)
        project_id_attr = self.get_attribute_model("project_id",
                                                   sample.project_id)

        attributes.append(resource_id_attr)
        attributes.append(user_id_attr)
        attributes.append(project_id_attr)

        return attributes

    @staticmethod
    def get_metrics_model(sample, data_points):
        name = sample.name.replace(".", "_")
        desc = str(sample.name) + " unit:" + sample.unit
        unit = sample.unit
        metrics = dict()
        metric_type = None
        if sample.type == smp.TYPE_CUMULATIVE:
            metric_type = "counter"
        else:
            metric_type = "gauge"
        metrics.update({
            "name": name,
            "description": desc,
            "unit": unit,
            metric_type: {"data_points": data_points}
        })
        return metrics

    @staticmethod
    def get_data_points_model(timestamp, attributes, volume):
        data_points = dict()
        struct_time = timeutils.parse_isotime(timestamp).timetuple()
        unix_time = int(time.mktime(struct_time))
        data_points.update({
            'attributes': attributes,
            "start_time_unix_nano": unix_time,
            "time_unix_nano": unix_time,
            "as_double": volume,
            "flags": 0
        })
        return data_points

    def get_data_model(self, sample, data_points):
        metrics = [self.get_metrics_model(sample, data_points)]
        data = {
            "resource_metrics": [{
                "scope_metrics": [{
                    "scope": {
                        "name": "ceilometer",
                        "version": "v1"
                    },
                    "metrics": metrics
                }]
            }]
        }
        return data

    def get_data_points(self, sample):
        # attributes contain basic metadata
        attributes = self.get_attributes_model(sample)
        try:
            return [self.get_data_points_model(
                sample.timestamp, attributes, sample.volume)]
        except Exception as e:
            LOG.warning("Get data point error, %s" % e)
            return []

    def get_opentelemetry_model(self, sample):
        data_points = self.get_data_points(sample)
        if data_points:
            data = self.get_data_model(sample, data_points)
            return data
        else:
            return None

    def publish_samples(self, samples):
        """Send a metering message for publishing

        :param samples: Samples from pipeline after transformation
        """
        if not samples:
            LOG.warning('Data samples is empty!')
            return

        for s in samples:
            data = self.get_opentelemetry_model(s)
            if data:
                self._do_post(json.dumps(data))

    @staticmethod
    def publish_events(events):
        raise NotImplementedError
