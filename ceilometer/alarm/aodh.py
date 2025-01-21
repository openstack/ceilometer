#
# Copyright 2025 Red Hat, Inc
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
"""Common code for working with alarm metrics
"""
from ceilometer.polling import plugin_base
from ceilometer import sample

DEFAULT_GROUP = "service_credentials"


class _Base(plugin_base.PollsterBase):
    @property
    def default_discovery(self):
        return 'alarm'


class EvaluationResultPollster(_Base):
    @staticmethod
    def get_evaluation_results_metrics(metrics):
        evaluation_metrics = []
        if "evaluation_results" in metrics:
            for metric in metrics["evaluation_results"]:
                for state, count in metric["state_counters"].items():
                    evaluation_metrics.append({
                        "name": "evaluation_result",
                        "state": state,
                        "count": count,
                        "project_id": metric['project_id'],
                        "alarm_id": metric['alarm_id']
                    })
        return evaluation_metrics

    def get_samples(self, manager, cache, resources):
        metrics = self.get_evaluation_results_metrics(resources[0])
        for metric in metrics:
            yield sample.Sample(
                name='alarm.' + metric['name'],
                type=sample.TYPE_GAUGE,
                volume=int(metric['count']),
                unit='evaluation_result_count',
                user_id=None,
                project_id=metric['project_id'],
                resource_id=metric['alarm_id'],
                resource_metadata={"alarm_state": metric['state']},
            )
