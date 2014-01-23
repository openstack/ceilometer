# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Intel Corp.
#
# Authors: Yunhong Jiang <yunhong.jiang@intel.com>
#          Julien Danjou <julien@danjou.info>
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

import datetime
import yaml

from stevedore import extension

from ceilometer.openstack.common.fixture import mockpatch
from ceilometer.openstack.common import test
from ceilometer.openstack.common import timeutils
from ceilometer import pipeline
from ceilometer import publisher
from ceilometer.publisher import test as test_publisher
from ceilometer import sample
from ceilometer import transformer
from ceilometer.transformer import accumulator
from ceilometer.transformer import conversions


class TestTransformerAccumulator(test.BaseTestCase):

    def test_handle_sample(self):
        test_sample = sample.Sample(
            name='a',
            type=sample.TYPE_GAUGE,
            volume=1,
            unit='B',
            user_id="test_user",
            project_id="test_proj",
            resource_id="test_resource",
            timestamp=timeutils.utcnow().isoformat(),
            resource_metadata={}
        )

        # Test when size is set to less than 1.
        tf = accumulator.TransformerAccumulator(size=0)
        self.assertEqual(tf.handle_sample(None, test_sample), test_sample)
        self.assertFalse(hasattr(tf, 'samples'))
        # Test when size is set to greater or equal than 1.
        tf = accumulator.TransformerAccumulator(size=2)
        tf.handle_sample(None, test_sample)
        self.assertEqual(len(tf.samples), 1)


class TestPipeline(test.BaseTestCase):
    def fake_tem_init(self):
        """Fake a transformerManager for pipeline
           The faked entry point setting is below:
           update: TransformerClass
           except: TransformerClassException
           drop:   TransformerClassDrop
        """
        pass

    def fake_tem_get_ext(self, name):
        class_name_ext = {
            'update': self.TransformerClass,
            'except': self.TransformerClassException,
            'drop': self.TransformerClassDrop,
            'cache': accumulator.TransformerAccumulator,
            'unit_conversion': conversions.ScalingTransformer,
            'rate_of_change': conversions.RateOfChangeTransformer,
        }

        if name in class_name_ext:
            return extension.Extension(name, None,
                                       class_name_ext[name],
                                       None,
                                       )

        raise KeyError(name)

    def get_publisher(self, url, namespace=''):
        fake_drivers = {'test://': test_publisher.TestPublisher,
                        'new://': test_publisher.TestPublisher,
                        'except://': self.PublisherClassException}
        return fake_drivers[url](url)

    class PublisherClassException(publisher.PublisherBase):
        def publish_samples(self, ctxt, counters):
            raise Exception()

    class TransformerClass(transformer.TransformerBase):
        samples = []

        def __init__(self, append_name='_update'):
            self.__class__.samples = []
            self.append_name = append_name

        def flush(self, ctxt):
            return []

        def handle_sample(self, ctxt, counter):
            self.__class__.samples.append(counter)
            newname = getattr(counter, 'name') + self.append_name
            return sample.Sample(
                name=newname,
                type=counter.type,
                volume=counter.volume,
                unit=counter.unit,
                user_id=counter.user_id,
                project_id=counter.project_id,
                resource_id=counter.resource_id,
                timestamp=counter.timestamp,
                resource_metadata=counter.resource_metadata,
            )

    class TransformerClassDrop(transformer.TransformerBase):
        samples = []

        def __init__(self):
            self.__class__.samples = []

        def handle_sample(self, ctxt, counter):
            self.__class__.samples.append(counter)

    class TransformerClassException(object):
        def handle_sample(self, ctxt, counter):
            raise Exception()

    def setUp(self):
        super(TestPipeline, self).setUp()

        self.test_counter = sample.Sample(
            name='a',
            type=sample.TYPE_GAUGE,
            volume=1,
            unit='B',
            user_id="test_user",
            project_id="test_proj",
            resource_id="test_resource",
            timestamp=timeutils.utcnow().isoformat(),
            resource_metadata={}
        )

        self.useFixture(mockpatch.PatchObject(
            transformer.TransformerExtensionManager, "__init__",
            side_effect=self.fake_tem_init))

        self.useFixture(mockpatch.PatchObject(
            transformer.TransformerExtensionManager, "get_ext",
            side_effect=self.fake_tem_get_ext))

        self.useFixture(mockpatch.PatchObject(
            publisher, 'get_publisher', side_effect=self.get_publisher))

        self.transformer_manager = transformer.TransformerExtensionManager()

        self.pipeline_cfg = [{
            'name': "test_pipeline",
            'interval': 5,
            'counters': ['a'],
            'transformers': [
                {'name': "update",
                 'parameters': {}}
            ],
            'publishers': ["test://"],
        }, ]

    def _exception_create_pipelinemanager(self):
        self.assertRaises(pipeline.PipelineException,
                          pipeline.PipelineManager,
                          self.pipeline_cfg,
                          self.transformer_manager)

    def test_no_counters(self):
        del self.pipeline_cfg[0]['counters']
        self._exception_create_pipelinemanager()

    def test_no_transformers(self):
        del self.pipeline_cfg[0]['transformers']
        self._exception_create_pipelinemanager()

    def test_no_name(self):
        del self.pipeline_cfg[0]['name']
        self._exception_create_pipelinemanager()

    def test_no_interval(self):
        del self.pipeline_cfg[0]['interval']
        self._exception_create_pipelinemanager()

    def test_no_publishers(self):
        del self.pipeline_cfg[0]['publishers']
        self._exception_create_pipelinemanager()

    def test_invalid_resources(self):
        invalid_resource = {'invalid': 1}
        self.pipeline_cfg[0]['resources'] = invalid_resource
        self._exception_create_pipelinemanager()

    def test_check_counters_include_exclude_same(self):
        counter_cfg = ['a', '!a']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        self._exception_create_pipelinemanager()

    def test_check_counters_include_exclude(self):
        counter_cfg = ['a', '!b']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        self._exception_create_pipelinemanager()

    def test_check_counters_wildcard_included(self):
        counter_cfg = ['a', '*']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        self._exception_create_pipelinemanager()

    def test_check_publishers_invalid_publisher(self):
        publisher_cfg = ['test_invalid']
        self.pipeline_cfg[0]['publishers'] = publisher_cfg

    def test_invalid_string_interval(self):
        self.pipeline_cfg[0]['interval'] = 'string'
        self._exception_create_pipelinemanager()

    def test_check_transformer_invalid_transformer(self):
        transformer_cfg = [
            {'name': "test_invalid",
             'parameters': {}}
        ]
        self.pipeline_cfg[0]['transformers'] = transformer_cfg
        self._exception_create_pipelinemanager()

    def test_get_interval(self):
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)

        pipe = pipeline_manager.pipelines[0]
        self.assertTrue(pipe.get_interval() == 5)

    def test_publisher_transformer_invoked(self):
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)

        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 1)
        self.assertTrue(len(self.TransformerClass.samples) == 1)
        self.assertEqual(getattr(publisher.samples[0], "name"), 'a_update')
        self.assertTrue(getattr(self.TransformerClass.samples[0], "name")
                        == 'a')

    def test_multiple_included_counters(self):
        counter_cfg = ['a', 'b']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)

        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 1)

        self.test_counter = sample.Sample(
            name='b',
            type=self.test_counter.type,
            volume=self.test_counter.volume,
            unit=self.test_counter.unit,
            user_id=self.test_counter.user_id,
            project_id=self.test_counter.project_id,
            resource_id=self.test_counter.resource_id,
            timestamp=self.test_counter.timestamp,
            resource_metadata=self.test_counter.resource_metadata,
        )

        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        self.assertEqual(len(publisher.samples), 2)
        self.assertTrue(len(self.TransformerClass.samples) == 2)
        self.assertEqual(getattr(publisher.samples[0], "name"), 'a_update')
        self.assertEqual(getattr(publisher.samples[1], "name"), 'b_update')

    def test_counter_dont_match(self):
        counter_cfg = ['nomatch']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 0)
        self.assertEqual(publisher.calls, 0)

    def test_wildcard_counter(self):
        counter_cfg = ['*']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 1)
        self.assertTrue(len(self.TransformerClass.samples) == 1)
        self.assertEqual(getattr(publisher.samples[0], "name"), 'a_update')

    def test_wildcard_excluded_counters(self):
        counter_cfg = ['*', '!a']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        self.assertFalse(pipeline_manager.pipelines[0].support_meter('a'))

    def test_wildcard_excluded_counters_not_excluded(self):
        counter_cfg = ['*', '!b']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])
        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 1)
        self.assertEqual(len(self.TransformerClass.samples), 1)
        self.assertEqual(getattr(publisher.samples[0], "name"),
                         'a_update')

    def test_all_excluded_counters_not_excluded(self):
        counter_cfg = ['!b', '!c']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 1)
        self.assertTrue(len(self.TransformerClass.samples) == 1)
        self.assertEqual(getattr(publisher.samples[0], "name"), 'a_update')
        self.assertTrue(getattr(self.TransformerClass.samples[0], "name")
                        == 'a')

    def test_all_excluded_counters_is_excluded(self):
        counter_cfg = ['!a', '!c']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        self.assertFalse(pipeline_manager.pipelines[0].support_meter('a'))
        self.assertTrue(pipeline_manager.pipelines[0].support_meter('b'))
        self.assertFalse(pipeline_manager.pipelines[0].support_meter('c'))

    def test_wildcard_and_excluded_wildcard_counters(self):
        counter_cfg = ['*', '!disk.*']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        self.assertFalse(pipeline_manager.pipelines[0].
                         support_meter('disk.read.bytes'))
        self.assertTrue(pipeline_manager.pipelines[0].support_meter('cpu'))

    def test_included_counter_and_wildcard_counters(self):
        counter_cfg = ['cpu', 'disk.*']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        self.assertTrue(pipeline_manager.pipelines[0].
                        support_meter('disk.read.bytes'))
        self.assertTrue(pipeline_manager.pipelines[0].support_meter('cpu'))
        self.assertFalse(pipeline_manager.pipelines[0].
                         support_meter('instance'))

    def test_excluded_counter_and_excluded_wildcard_counters(self):
        counter_cfg = ['!cpu', '!disk.*']
        self.pipeline_cfg[0]['counters'] = counter_cfg
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        self.assertFalse(pipeline_manager.pipelines[0].
                         support_meter('disk.read.bytes'))
        self.assertFalse(pipeline_manager.pipelines[0].support_meter('cpu'))
        self.assertTrue(pipeline_manager.pipelines[0].
                        support_meter('instance'))

    def test_multiple_pipeline(self):
        self.pipeline_cfg.append({
            'name': 'second_pipeline',
            'interval': 5,
            'counters': ['b'],
            'transformers': [{
                'name': 'update',
                'parameters':
                {
                    "append_name": "_new",
                }
            }],
            'publishers': ['new'],
        })

        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        self.test_counter = sample.Sample(
            name='b',
            type=self.test_counter.type,
            volume=self.test_counter.volume,
            unit=self.test_counter.unit,
            user_id=self.test_counter.user_id,
            project_id=self.test_counter.project_id,
            resource_id=self.test_counter.resource_id,
            timestamp=self.test_counter.timestamp,
            resource_metadata=self.test_counter.resource_metadata,
        )

        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 1)
        self.assertEqual(publisher.calls, 1)
        self.assertEqual(getattr(publisher.samples[0], "name"), 'a_update')
        new_publisher = pipeline_manager.pipelines[1].publishers[0]
        self.assertEqual(len(new_publisher.samples), 1)
        self.assertEqual(new_publisher.calls, 1)
        self.assertEqual(getattr(new_publisher.samples[0], "name"), 'b_new')
        self.assertTrue(getattr(self.TransformerClass.samples[0], "name")
                        == 'a')

        self.assertTrue(len(self.TransformerClass.samples) == 2)
        self.assertTrue(getattr(self.TransformerClass.samples[0], "name")
                        == 'a')
        self.assertTrue(getattr(self.TransformerClass.samples[1], "name")
                        == 'b')

    def test_multiple_pipeline_exception(self):
        self.pipeline_cfg.append({
            'name': "second_pipeline",
            "interval": 5,
            'counters': ['b'],
            'transformers': [{
                'name': 'update',
                'parameters':
                {
                    "append_name": "_new",
                }
            }],
            'publishers': ['except'],
        })
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)

        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        self.test_counter = sample.Sample(
            name='b',
            type=self.test_counter.type,
            volume=self.test_counter.volume,
            unit=self.test_counter.unit,
            user_id=self.test_counter.user_id,
            project_id=self.test_counter.project_id,
            resource_id=self.test_counter.resource_id,
            timestamp=self.test_counter.timestamp,
            resource_metadata=self.test_counter.resource_metadata,
        )

        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(publisher.calls, 1)
        self.assertEqual(len(publisher.samples), 1)
        self.assertEqual(getattr(publisher.samples[0], "name"), 'a_update')
        self.assertTrue(len(self.TransformerClass.samples) == 2)
        self.assertTrue(getattr(self.TransformerClass.samples[0], "name")
                        == 'a')
        self.assertTrue(getattr(self.TransformerClass.samples[1], "name")
                        == 'b')

    def test_none_transformer_pipeline(self):
        self.pipeline_cfg[0]['transformers'] = None
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])
        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 1)
        self.assertEqual(publisher.calls, 1)
        self.assertEqual(getattr(publisher.samples[0], 'name'), 'a')

    def test_empty_transformer_pipeline(self):
        self.pipeline_cfg[0]['transformers'] = []
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])
        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 1)
        self.assertEqual(publisher.calls, 1)
        self.assertEqual(getattr(publisher.samples[0], 'name'), 'a')

    def test_multiple_transformer_same_class(self):
        self.pipeline_cfg[0]['transformers'] = [
            {
                'name': 'update',
                'parameters': {}
            },
            {
                'name': 'update',
                'parameters': {}
            },
        ]
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)

        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(publisher.calls, 1)
        self.assertEqual(len(publisher.samples), 1)
        self.assertEqual(getattr(publisher.samples[0], 'name'),
                         'a_update_update')
        self.assertTrue(len(self.TransformerClass.samples) == 2)
        self.assertTrue(getattr(self.TransformerClass.samples[0], 'name')
                        == 'a')
        self.assertTrue(getattr(self.TransformerClass.samples[1], 'name')
                        == 'a_update')

    def test_multiple_transformer_same_class_different_parameter(self):
        self.pipeline_cfg[0]['transformers'] = [
            {
                'name': 'update',
                'parameters':
                {
                    "append_name": "_update",
                }
            },
            {
                'name': 'update',
                'parameters':
                {
                    "append_name": "_new",
                }
            },
        ]
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        self.assertTrue(len(self.TransformerClass.samples) == 2)
        self.assertTrue(getattr(self.TransformerClass.samples[0], 'name')
                        == 'a')
        self.assertTrue(getattr(self.TransformerClass.samples[1], 'name')
                        == 'a_update')
        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 1)
        self.assertEqual(getattr(publisher.samples[0], 'name'),
                         'a_update_new')

    def test_multiple_transformer_drop_transformer(self):
        self.pipeline_cfg[0]['transformers'] = [
            {
                'name': 'update',
                'parameters':
                {
                    "append_name": "_update",
                }
            },
            {
                'name': 'drop',
                'parameters': {}
            },
            {
                'name': 'update',
                'parameters':
                {
                    "append_name": "_new",
                }
            },
        ]
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 0)
        self.assertTrue(len(self.TransformerClass.samples) == 1)
        self.assertTrue(getattr(self.TransformerClass.samples[0], 'name')
                        == 'a')
        self.assertTrue(len(self.TransformerClassDrop.samples) == 1)
        self.assertTrue(getattr(self.TransformerClassDrop.samples[0], 'name')
                        == 'a_update')

    def test_multiple_publisher(self):
        self.pipeline_cfg[0]['publishers'] = ['test://', 'new://']
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)

        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        new_publisher = pipeline_manager.pipelines[0].publishers[1]
        self.assertEqual(len(publisher.samples), 1)
        self.assertEqual(len(new_publisher.samples), 1)
        self.assertEqual(getattr(new_publisher.samples[0], 'name'),
                         'a_update')
        self.assertEqual(getattr(publisher.samples[0], 'name'),
                         'a_update')

    def test_multiple_publisher_isolation(self):
        self.pipeline_cfg[0]['publishers'] = ['except://', 'new://']
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        new_publisher = pipeline_manager.pipelines[0].publishers[1]
        self.assertEqual(len(new_publisher.samples), 1)
        self.assertEqual(getattr(new_publisher.samples[0], 'name'),
                         'a_update')

    def test_multiple_counter_pipeline(self):
        self.pipeline_cfg[0]['counters'] = ['a', 'b']
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        with pipeline_manager.publisher(None) as p:
            p([self.test_counter,
               sample.Sample(
                   name='b',
                   type=self.test_counter.type,
                   volume=self.test_counter.volume,
                   unit=self.test_counter.unit,
                   user_id=self.test_counter.user_id,
                   project_id=self.test_counter.project_id,
                   resource_id=self.test_counter.resource_id,
                   timestamp=self.test_counter.timestamp,
                   resource_metadata=self.test_counter.resource_metadata,
               )])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 2)
        self.assertEqual(getattr(publisher.samples[0], 'name'), 'a_update')
        self.assertEqual(getattr(publisher.samples[1], 'name'), 'b_update')

    def test_flush_pipeline_cache(self):
        CACHE_SIZE = 10
        self.pipeline_cfg[0]['transformers'].extend([
            {
                'name': 'cache',
                'parameters': {
                    'size': CACHE_SIZE,
                }
            },
            {
                'name': 'update',
                'parameters':
                {
                    'append_name': '_new'
                }
            }, ]
        )
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        pipe = pipeline_manager.pipelines[0]

        pipe.publish_sample(None, self.test_counter)
        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 0)
        pipe.flush(None)
        self.assertEqual(len(publisher.samples), 0)
        pipe.publish_sample(None, self.test_counter)
        pipe.flush(None)
        self.assertEqual(len(publisher.samples), 0)
        for i in range(CACHE_SIZE - 2):
            pipe.publish_sample(None, self.test_counter)
        pipe.flush(None)
        self.assertEqual(len(publisher.samples), CACHE_SIZE)
        self.assertTrue(getattr(publisher.samples[0], 'name')
                        == 'a_update_new')

    def test_flush_pipeline_cache_multiple_counter(self):
        CACHE_SIZE = 3
        self.pipeline_cfg[0]['transformers'].extend([
            {
                'name': 'cache',
                'parameters': {
                    'size': CACHE_SIZE
                }
            },
            {
                'name': 'update',
                'parameters':
                {
                    'append_name': '_new'
                }
            }, ]
        )
        self.pipeline_cfg[0]['counters'] = ['a', 'b']
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        with pipeline_manager.publisher(None) as p:
            p([self.test_counter,
               sample.Sample(
                   name='b',
                   type=self.test_counter.type,
                   volume=self.test_counter.volume,
                   unit=self.test_counter.unit,
                   user_id=self.test_counter.user_id,
                   project_id=self.test_counter.project_id,
                   resource_id=self.test_counter.resource_id,
                   timestamp=self.test_counter.timestamp,
                   resource_metadata=self.test_counter.resource_metadata,
               )])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 0)

        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        self.assertEqual(len(publisher.samples), CACHE_SIZE)
        self.assertEqual(getattr(publisher.samples[0], 'name'),
                         'a_update_new')
        self.assertEqual(getattr(publisher.samples[1], 'name'),
                         'b_update_new')

    def test_flush_pipeline_cache_before_publisher(self):
        self.pipeline_cfg[0]['transformers'].append({
            'name': 'cache',
            'parameters': {}
        })
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        pipe = pipeline_manager.pipelines[0]

        publisher = pipe.publishers[0]
        pipe.publish_sample(None, self.test_counter)
        self.assertEqual(len(publisher.samples), 0)
        pipe.flush(None)
        self.assertEqual(len(publisher.samples), 1)
        self.assertEqual(getattr(publisher.samples[0], 'name'),
                         'a_update')

    def test_variable_counter(self):
        self.pipeline_cfg = [{
            'name': "test_pipeline",
            'interval': 5,
            'counters': ['a:*'],
            'transformers': [
                {'name': "update",
                 'parameters': {}}
            ],
            'publishers': ["test://"],
        }, ]
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)

        self.test_counter = sample.Sample(
            name='a:b',
            type=self.test_counter.type,
            volume=self.test_counter.volume,
            unit=self.test_counter.unit,
            user_id=self.test_counter.user_id,
            project_id=self.test_counter.project_id,
            resource_id=self.test_counter.resource_id,
            timestamp=self.test_counter.timestamp,
            resource_metadata=self.test_counter.resource_metadata,
        )

        with pipeline_manager.publisher(None) as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 1)
        self.assertTrue(len(self.TransformerClass.samples) == 1)
        self.assertEqual(getattr(publisher.samples[0], "name"),
                         'a:b_update')
        self.assertTrue(getattr(self.TransformerClass.samples[0], "name")
                        == 'a:b')

    def test_global_unit_conversion(self):
        scale = 'volume / ((10**6) * 60)'
        self.pipeline_cfg[0]['transformers'] = [
            {
                'name': 'unit_conversion',
                'parameters': {
                    'source': {},
                    'target': {'name': 'cpu_mins',
                               'unit': 'min',
                               'scale': scale},
                }
            },
        ]
        self.pipeline_cfg[0]['counters'] = ['cpu']
        counters = [
            sample.Sample(
                name='cpu',
                type=sample.TYPE_CUMULATIVE,
                volume=1200000000,
                unit='ns',
                user_id='test_user',
                project_id='test_proj',
                resource_id='test_resource',
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata={}
            ),
        ]

        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        pipe = pipeline_manager.pipelines[0]

        pipe.publish_samples(None, counters)
        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 1)
        pipe.flush(None)
        self.assertEqual(len(publisher.samples), 1)
        cpu_mins = publisher.samples[-1]
        self.assertEqual(getattr(cpu_mins, 'name'), 'cpu_mins')
        self.assertEqual(getattr(cpu_mins, 'unit'), 'min')
        self.assertEqual(getattr(cpu_mins, 'type'), sample.TYPE_CUMULATIVE)
        self.assertEqual(getattr(cpu_mins, 'volume'), 20)

    def test_unit_identified_source_unit_conversion(self):
        self.pipeline_cfg[0]['transformers'] = [
            {
                'name': 'unit_conversion',
                'parameters': {
                    'source': {'unit': '°C'},
                    'target': {'unit': '°F',
                               'scale': '(volume * 1.8) + 32'},
                }
            },
        ]
        self.pipeline_cfg[0]['counters'] = ['core_temperature',
                                            'ambient_temperature']
        counters = [
            sample.Sample(
                name='core_temperature',
                type=sample.TYPE_GAUGE,
                volume=36.0,
                unit='°C',
                user_id='test_user',
                project_id='test_proj',
                resource_id='test_resource',
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata={}
            ),
            sample.Sample(
                name='ambient_temperature',
                type=sample.TYPE_GAUGE,
                volume=88.8,
                unit='°F',
                user_id='test_user',
                project_id='test_proj',
                resource_id='test_resource',
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata={}
            ),
        ]

        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        pipe = pipeline_manager.pipelines[0]

        pipe.publish_samples(None, counters)
        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 2)
        core_temp = publisher.samples[1]
        self.assertEqual(getattr(core_temp, 'name'), 'core_temperature')
        self.assertEqual(getattr(core_temp, 'unit'), '°F')
        self.assertEqual(getattr(core_temp, 'volume'), 96.8)
        amb_temp = publisher.samples[0]
        self.assertEqual(getattr(amb_temp, 'name'), 'ambient_temperature')
        self.assertEqual(getattr(amb_temp, 'unit'), '°F')
        self.assertEqual(getattr(amb_temp, 'volume'), 88.8)
        self.assertEqual(getattr(core_temp, 'volume'), 96.8)

    def _do_test_rate_of_change_conversion(self, prev, curr, type, expected,
                                           offset=1, weight=None):
        s = "(resource_metadata.user_metadata.autoscaling_weight or 1.0)" \
            "* (resource_metadata.non.existent or 1.0)" \
            "* (100.0 / (10**9 * (resource_metadata.cpu_number or 1)))"
        self.pipeline_cfg[0]['transformers'] = [
            {
                'name': 'rate_of_change',
                'parameters': {
                    'source': {},
                    'target': {'name': 'cpu_util',
                               'unit': '%',
                               'type': sample.TYPE_GAUGE,
                               'scale': s},
                }
            },
        ]
        self.pipeline_cfg[0]['counters'] = ['cpu']
        now = timeutils.utcnow()
        later = now + datetime.timedelta(minutes=offset)
        um = {'autoscaling_weight': weight} if weight else {}
        counters = [
            sample.Sample(
                name='cpu',
                type=type,
                volume=prev,
                unit='ns',
                user_id='test_user',
                project_id='test_proj',
                resource_id='test_resource',
                timestamp=now.isoformat(),
                resource_metadata={'cpu_number': 4,
                                   'user_metadata': um},
            ),
            sample.Sample(
                name='cpu',
                type=type,
                volume=prev,
                unit='ns',
                user_id='test_user',
                project_id='test_proj',
                resource_id='test_resource2',
                timestamp=now.isoformat(),
                resource_metadata={'cpu_number': 2,
                                   'user_metadata': um},
            ),
            sample.Sample(
                name='cpu',
                type=type,
                volume=curr,
                unit='ns',
                user_id='test_user',
                project_id='test_proj',
                resource_id='test_resource',
                timestamp=later.isoformat(),
                resource_metadata={'cpu_number': 4,
                                   'user_metadata': um},
            ),
            sample.Sample(
                name='cpu',
                type=type,
                volume=curr,
                unit='ns',
                user_id='test_user',
                project_id='test_proj',
                resource_id='test_resource2',
                timestamp=later.isoformat(),
                resource_metadata={'cpu_number': 2,
                                   'user_metadata': um},
            ),
        ]

        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        pipe = pipeline_manager.pipelines[0]

        pipe.publish_samples(None, counters)
        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 2)
        pipe.flush(None)
        self.assertEqual(len(publisher.samples), 2)
        cpu_util = publisher.samples[0]
        self.assertEqual(getattr(cpu_util, 'name'), 'cpu_util')
        self.assertEqual(getattr(cpu_util, 'resource_id'), 'test_resource')
        self.assertEqual(getattr(cpu_util, 'unit'), '%')
        self.assertEqual(getattr(cpu_util, 'type'), sample.TYPE_GAUGE)
        self.assertEqual(getattr(cpu_util, 'volume'), expected)
        cpu_util = publisher.samples[1]
        self.assertEqual(getattr(cpu_util, 'name'), 'cpu_util')
        self.assertEqual(getattr(cpu_util, 'resource_id'), 'test_resource2')
        self.assertEqual(getattr(cpu_util, 'unit'), '%')
        self.assertEqual(getattr(cpu_util, 'type'), sample.TYPE_GAUGE)
        self.assertEqual(getattr(cpu_util, 'volume'), expected * 2)

    def test_rate_of_change_conversion(self):
        self._do_test_rate_of_change_conversion(120000000000,
                                                180000000000,
                                                sample.TYPE_CUMULATIVE,
                                                25.0)

    def test_rate_of_change_conversion_weight(self):
        self._do_test_rate_of_change_conversion(120000000000,
                                                180000000000,
                                                sample.TYPE_CUMULATIVE,
                                                27.5,
                                                weight=1.1)

    def test_rate_of_change_conversion_negative_cumulative_delta(self):
        self._do_test_rate_of_change_conversion(180000000000,
                                                120000000000,
                                                sample.TYPE_CUMULATIVE,
                                                50.0)

    def test_rate_of_change_conversion_negative_gauge_delta(self):
        self._do_test_rate_of_change_conversion(180000000000,
                                                120000000000,
                                                sample.TYPE_GAUGE,
                                                -25.0)

    def test_rate_of_change_conversion_zero_delay(self):
        self._do_test_rate_of_change_conversion(120000000000,
                                                120000000000,
                                                sample.TYPE_CUMULATIVE,
                                                0.0,
                                                offset=0)

    def test_rate_of_change_no_predecessor(self):
        s = "100.0 / (10**9 * resource_metadata.get('cpu_number', 1))"
        self.pipeline_cfg[0]['transformers'] = [
            {
                'name': 'rate_of_change',
                'parameters': {
                    'source': {},
                    'target': {'name': 'cpu_util',
                               'unit': '%',
                               'type': sample.TYPE_GAUGE,
                               'scale': s}
                }
            },
        ]
        self.pipeline_cfg[0]['counters'] = ['cpu']
        now = timeutils.utcnow()
        counters = [
            sample.Sample(
                name='cpu',
                type=sample.TYPE_CUMULATIVE,
                volume=120000000000,
                unit='ns',
                user_id='test_user',
                project_id='test_proj',
                resource_id='test_resource',
                timestamp=now.isoformat(),
                resource_metadata={'cpu_number': 4}
            ),
        ]

        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        pipe = pipeline_manager.pipelines[0]

        pipe.publish_samples(None, counters)
        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(len(publisher.samples), 0)
        pipe.flush(None)
        self.assertEqual(len(publisher.samples), 0)

    def test_resources(self):
        resources = ['test1://', 'test2://']
        self.pipeline_cfg[0]['resources'] = resources
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        self.assertEqual(pipeline_manager.pipelines[0].resources,
                         resources)

    def test_no_resources(self):
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        self.assertEqual(len(pipeline_manager.pipelines[0].resources),
                         0)

    def _do_test_rate_of_change_mapping(self, pipe, meters, units):
        now = timeutils.utcnow()
        base = 1000
        offset = 7
        rate = 42
        later = now + datetime.timedelta(minutes=offset)
        counters = []
        for v, ts in [(base, now.isoformat()),
                      (base + (offset * 60 * rate), later.isoformat())]:
            for n, u, r in [(meters[0], units[0], 'resource1'),
                            (meters[1], units[1], 'resource2')]:
                s = sample.Sample(
                    name=n,
                    type=sample.TYPE_CUMULATIVE,
                    volume=v,
                    unit=u,
                    user_id='test_user',
                    project_id='test_proj',
                    resource_id=r,
                    timestamp=ts,
                    resource_metadata={},
                )
                counters.append(s)

        pipe.publish_samples(None, counters)
        publisher = pipe.publishers[0]
        self.assertEqual(len(publisher.samples), 2)
        pipe.flush(None)
        self.assertEqual(len(publisher.samples), 2)
        bps = publisher.samples[0]
        self.assertEqual(getattr(bps, 'name'), '%s.rate' % meters[0])
        self.assertEqual(getattr(bps, 'resource_id'), 'resource1')
        self.assertEqual(getattr(bps, 'unit'), '%s/s' % units[0])
        self.assertEqual(getattr(bps, 'type'), sample.TYPE_GAUGE)
        self.assertEqual(getattr(bps, 'volume'), rate)
        rps = publisher.samples[1]
        self.assertEqual(getattr(rps, 'name'), '%s.rate' % meters[1])
        self.assertEqual(getattr(rps, 'resource_id'), 'resource2')
        self.assertEqual(getattr(rps, 'unit'), '%s/s' % units[1])
        self.assertEqual(getattr(rps, 'type'), sample.TYPE_GAUGE)
        self.assertEqual(getattr(rps, 'volume'), rate)

    def test_rate_of_change_mapping(self):
        map_from = {'name': 'disk\\.(read|write)\\.(bytes|requests)',
                    'unit': '(B|request)'}
        map_to = {'name': 'disk.\\1.\\2.rate',
                  'unit': '\\1/s'}
        self.pipeline_cfg[0]['transformers'] = [
            {
                'name': 'rate_of_change',
                'parameters': {
                    'source': {
                        'map_from': map_from
                    },
                    'target': {
                        'map_to': map_to,
                        'type': sample.TYPE_GAUGE
                    },
                },
            },
        ]
        self.pipeline_cfg[0]['counters'] = ['disk.read.bytes',
                                            'disk.write.requests']
        pipeline_manager = pipeline.PipelineManager(self.pipeline_cfg,
                                                    self.transformer_manager)
        pipe = pipeline_manager.pipelines[0]
        meters = ('disk.read.bytes', 'disk.write.requests')
        units = ('B', 'request')
        self._do_test_rate_of_change_mapping(pipe, meters, units)

    def _do_test_rate_of_change_in_boilerplate_pipeline_cfg(self, index,
                                                            meters, units):
        with open('etc/ceilometer/pipeline.yaml') as fap:
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
