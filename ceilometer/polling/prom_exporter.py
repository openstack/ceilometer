#
# Copyright 2024 Juan Larriba
# Copyright 2024 Red Hat, Inc
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

import prometheus_client as prom

CEILOMETER_REGISTRY = prom.CollectorRegistry()


def export(prometheus_iface, prometheus_port):
    prom.start_http_server(port=prometheus_port,
                           addr=prometheus_iface,
                           registry=CEILOMETER_REGISTRY)


def collect_metrics(samples):
    metric_cleared = False

    for sample in samples:
        name = "ceilometer_" + sample['counter_name'].replace('.', '_')
        labels = _gen_labels(sample)

        metric = CEILOMETER_REGISTRY._names_to_collectors.get(name, None)

        # NOTE: Ungregister the metric at the first iteration to purge stale
        # samples
        if not metric_cleared:
            if metric:
                CEILOMETER_REGISTRY.unregister(metric)
                metric = None
            metric_cleared = True

        if metric is None:
            metric = prom.Gauge(name=name, documentation="",
                                labelnames=labels['keys'],
                                registry=CEILOMETER_REGISTRY)
        metric.labels(*labels['values']).set(sample['counter_volume'])


def _gen_labels(sample):
    labels = dict(keys=[], values=[])
    cNameShards = sample['counter_name'].split(".")
    ctype = ''

    plugin = cNameShards[0]
    pluginVal = sample['resource_id']
    if len(cNameShards) > 2:
        pluginVal = cNameShards[2]

    if len(cNameShards) > 1:
        ctype = cNameShards[1]
    else:
        ctype = cNameShards[0]

    labels['keys'].append(plugin)
    labels['values'].append(pluginVal)

    labels['keys'].append("publisher")
    labels['values'].append("ceilometer")

    labels['keys'].append("type")
    labels['values'].append(ctype)

    if sample.get('counter_name'):
        labels['keys'].append("counter")
        labels['values'].append(sample['counter_name'])

    if sample.get('project_id'):
        labels['keys'].append("project")
        labels['values'].append(sample['project_id'])

    if sample.get('project_name'):
        labels['keys'].append("project_name")
        labels['values'].append(sample['project_name'])

    if sample.get('user_id'):
        labels['keys'].append("user")
        labels['values'].append(sample['user_id'])

    if sample.get('user_name'):
        labels['keys'].append("user_name")
        labels['values'].append(sample['user_name'])

    if sample.get('counter_unit'):
        labels['keys'].append("unit")
        labels['values'].append(sample['counter_unit'])

    if sample.get('resource_id'):
        labels['keys'].append("resource")
        labels['values'].append(sample['resource_id'])

    if sample.get('resource_metadata'):
        resource_metadata = sample['resource_metadata']

        if resource_metadata.get('host'):
            labels['keys'].append("vm_instance")
            labels['values'].append(resource_metadata['host'])

        if resource_metadata.get('display_name'):
            value = resource_metadata['display_name']
            if resource_metadata.get('name'):
                value = ':'.join([value, resource_metadata['name']])
            labels['keys'].append("resource_name")
            labels['values'].append(value)
        elif resource_metadata.get('name'):
            labels['keys'].append("resource_name")
            labels['values'].append(resource_metadata['name'])

        # NOTE(jwysogla): The prometheus_client library doesn't support
        # variable count of labels for the same metric. That's why the
        # prometheus exporter cannot support custom metric labels added
        # with the --property metering.<label_key>=<label_value> when
        # creating a server. This still works with publishers though.
        # The "server_group" label is used for autoscaling and so it's
        # the only one getting parsed. To always have the same number
        # of labels, it's added to all metrics and where there isn't a
        # value defined, it's substituted with "none".
        user_metadata = resource_metadata.get('user_metadata', {})
        if user_metadata.get('server_group'):
            labels['keys'].append('server_group')
            labels['values'].append(user_metadata['server_group'])
        else:
            labels['keys'].append('server_group')
            labels['values'].append('none')

    return labels
