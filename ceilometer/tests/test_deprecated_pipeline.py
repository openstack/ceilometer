#
# Copyright 2014 Red Hat, Inc
#
# Author: Eoghan Glynn <eglynn@redhat.com>
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

import yaml

from ceilometer import pipeline
from ceilometer.tests import pipeline_base


class TestDeprecatedPipeline(pipeline_base.BasePipelineTestCase):
    def _setup_pipeline_cfg(self):
        self.pipeline_cfg = [{
            'name': 'test_pipeline',
            'interval': 5,
            'counters': ['a'],
            'transformers': [
                {'name': 'update',
                 'parameters': {}}
            ],
            'publishers': ['test://'],
        }, ]

    def _augment_pipeline_cfg(self):
        self.pipeline_cfg.append({
            'name': 'second_pipeline',
            'interval': 5,
            'counters': ['b'],
            'transformers': [{
                'name': 'update',
                'parameters':
                {
                    'append_name': '_new',
                }
            }],
            'publishers': ['new'],
        })

    def _break_pipeline_cfg(self):
        self.pipeline_cfg.append({
            'name': 'second_pipeline',
            'interval': 5,
            'counters': ['b'],
            'transformers': [{
                'name': 'update',
                'parameters':
                {
                    'append_name': '_new',
                }
            }],
            'publishers': ['except'],
        })

    def _set_pipeline_cfg(self, field, value):
        self.pipeline_cfg[0][field] = value

    def _extend_pipeline_cfg(self, field, value):
        self.pipeline_cfg[0][field].extend(value)

    def _unset_pipeline_cfg(self, field):
        del self.pipeline_cfg[0][field]

    def _do_test_rate_of_change_in_boilerplate_pipeline_cfg(self, index,
                                                            meters, units):
        with open('etc/ceilometer/deprecated_pipeline.yaml') as fap:
            data = fap.read()
        pipeline_cfg = yaml.safe_load(data)
        for p in pipeline_cfg:
            p['publishers'] = ['test://']
        pipeline_manager = pipeline.PipelineManager(pipeline_cfg,
                                                    self.transformer_manager)
        pipe = pipeline_manager.pipelines[index]
        self._do_test_rate_of_change_mapping(pipe, meters, units)

    def test_rate_of_change_boilerplate_disk_read_cfg(self):
        meters = ('disk.read.bytes', 'disk.read.requests')
        units = ('B', 'request')
        self._do_test_rate_of_change_in_boilerplate_pipeline_cfg(2,
                                                                 meters,
                                                                 units)

    def test_rate_of_change_boilerplate_disk_write_cfg(self):
        meters = ('disk.write.bytes', 'disk.write.requests')
        units = ('B', 'request')
        self._do_test_rate_of_change_in_boilerplate_pipeline_cfg(2,
                                                                 meters,
                                                                 units)

    def test_rate_of_change_boilerplate_network_incoming_cfg(self):
        meters = ('network.incoming.bytes', 'network.incoming.packets')
        units = ('B', 'packet')
        self._do_test_rate_of_change_in_boilerplate_pipeline_cfg(3,
                                                                 meters,
                                                                 units)

    def test_rate_of_change_boilerplate_network_outgoing_cfg(self):
        meters = ('network.outgoing.bytes', 'network.outgoing.packets')
        units = ('B', 'packet')
        self._do_test_rate_of_change_in_boilerplate_pipeline_cfg(3,
                                                                 meters,
                                                                 units)
