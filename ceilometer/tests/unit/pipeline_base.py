# -*- coding: utf-8 -*-
#
# Copyright 2013 Intel Corp.
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
import traceback

import fixtures
import mock
from oslo_utils import timeutils
import six

from ceilometer.pipeline import base as pipe_base
from ceilometer.pipeline import sample as pipeline
from ceilometer import publisher
from ceilometer.publisher import test as test_publisher
from ceilometer import sample
from ceilometer import service
from ceilometer.tests import base


@six.add_metaclass(abc.ABCMeta)
class BasePipelineTestCase(base.BaseTestCase):

    def get_publisher(self, conf, url, namespace=''):
        fake_drivers = {'test://': test_publisher.TestPublisher,
                        'new://': test_publisher.TestPublisher,
                        'except://': self.PublisherClassException}
        return fake_drivers[url](conf, url)

    class PublisherClassException(publisher.ConfigPublisherBase):
        def publish_samples(self, samples):
            raise Exception()

        def publish_events(self, events):
            raise Exception()

    def setUp(self):
        super(BasePipelineTestCase, self).setUp()
        self.CONF = service.prepare_service([], [])

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

        self.useFixture(fixtures.MockPatchObject(
            publisher, 'get_publisher', side_effect=self.get_publisher))

        self._setup_pipeline_cfg()

        self._reraise_exception = True
        self.useFixture(fixtures.MockPatch(
            'ceilometer.pipeline.base.LOG.exception',
            side_effect=self._handle_reraise_exception))

    def _handle_reraise_exception(self, *args, **kwargs):
        if self._reraise_exception:
            raise Exception(traceback.format_exc())

    @abc.abstractmethod
    def _setup_pipeline_cfg(self):
        """Setup the appropriate form of pipeline config."""

    @abc.abstractmethod
    def _augment_pipeline_cfg(self):
        """Augment the pipeline config with an additional element."""

    @abc.abstractmethod
    def _break_pipeline_cfg(self):
        """Break the pipeline config with a malformed element."""

    @abc.abstractmethod
    def _dup_pipeline_name_cfg(self):
        """Break the pipeline config with duplicate pipeline name."""

    @abc.abstractmethod
    def _set_pipeline_cfg(self, field, value):
        """Set a field to a value in the pipeline config."""

    @abc.abstractmethod
    def _extend_pipeline_cfg(self, field, value):
        """Extend an existing field in the pipeline config with a value."""

    @abc.abstractmethod
    def _unset_pipeline_cfg(self, field):
        """Clear an existing field in the pipeline config."""

    def _build_and_set_new_pipeline(self):
        name = self.cfg2file(self.pipeline_cfg)
        self.CONF.set_override('pipeline_cfg_file', name)

    def _exception_create_pipelinemanager(self):
        self._build_and_set_new_pipeline()
        self.assertRaises(pipe_base.PipelineException,
                          pipeline.SamplePipelineManager, self.CONF)

    def test_no_meters(self):
        self._unset_pipeline_cfg('meters')
        self._exception_create_pipelinemanager()

    def test_no_name(self):
        self._unset_pipeline_cfg('name')
        self._exception_create_pipelinemanager()

    def test_no_publishers(self):
        self._unset_pipeline_cfg('publishers')
        self._exception_create_pipelinemanager()

    def test_check_counters_include_exclude_same(self):
        counter_cfg = ['a', '!a']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._exception_create_pipelinemanager()

    def test_check_counters_include_exclude(self):
        counter_cfg = ['a', '!b']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._exception_create_pipelinemanager()

    def test_check_counters_wildcard_included(self):
        counter_cfg = ['a', '*']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._exception_create_pipelinemanager()

    def test_check_publishers_invalid_publisher(self):
        publisher_cfg = ['test_invalid']
        self._set_pipeline_cfg('publishers', publisher_cfg)

    def test_multiple_included_counters(self):
        counter_cfg = ['a', 'b']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        with pipeline_manager.publisher() as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(1, len(publisher.samples))

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

        with pipeline_manager.publisher() as p:
            p([self.test_counter])

        self.assertEqual(2, len(publisher.samples))
        self.assertEqual('a', getattr(publisher.samples[0], "name"))
        self.assertEqual('b', getattr(publisher.samples[1], "name"))

    @mock.patch('ceilometer.pipeline.sample.LOG')
    def test_none_volume_counter(self, LOG):
        self._set_pipeline_cfg('meters', ['empty_volume'])
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        publisher = pipeline_manager.pipelines[0].publishers[0]

        test_s = sample.Sample(
            name='empty_volume',
            type=self.test_counter.type,
            volume=None,
            unit=self.test_counter.unit,
            user_id=self.test_counter.user_id,
            project_id=self.test_counter.project_id,
            resource_id=self.test_counter.resource_id,
            timestamp=self.test_counter.timestamp,
            resource_metadata=self.test_counter.resource_metadata,
        )

        with pipeline_manager.publisher() as p:
            p([test_s])

        LOG.warning.assert_called_once_with(
            'metering data %(counter_name)s for %(resource_id)s '
            '@ %(timestamp)s has no volume (volume: %(counter_volume)s), the '
            'sample will be dropped'
            % {'counter_name': test_s.name,
               'resource_id': test_s.resource_id,
               'timestamp': test_s.timestamp,
               'counter_volume': test_s.volume})

        self.assertEqual(0, len(publisher.samples))

    @mock.patch('ceilometer.pipeline.sample.LOG')
    def test_fake_volume_counter(self, LOG):
        self._set_pipeline_cfg('meters', ['fake_volume'])
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        publisher = pipeline_manager.pipelines[0].publishers[0]

        test_s = sample.Sample(
            name='fake_volume',
            type=self.test_counter.type,
            volume='fake_value',
            unit=self.test_counter.unit,
            user_id=self.test_counter.user_id,
            project_id=self.test_counter.project_id,
            resource_id=self.test_counter.resource_id,
            timestamp=self.test_counter.timestamp,
            resource_metadata=self.test_counter.resource_metadata,
        )

        with pipeline_manager.publisher() as p:
            p([test_s])

        LOG.warning.assert_called_once_with(
            'metering data %(counter_name)s for %(resource_id)s '
            '@ %(timestamp)s has volume which is not a number '
            '(volume: %(counter_volume)s), the sample will be dropped'
            % {'counter_name': test_s.name,
               'resource_id': test_s.resource_id,
               'timestamp': test_s.timestamp,
               'counter_volume': test_s.volume})

        self.assertEqual(0, len(publisher.samples))

    def test_counter_dont_match(self):
        counter_cfg = ['nomatch']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        with pipeline_manager.publisher() as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(0, len(publisher.samples))
        self.assertEqual(0, publisher.calls)

    def test_wildcard_counter(self):
        counter_cfg = ['*']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        with pipeline_manager.publisher() as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(1, len(publisher.samples))
        self.assertEqual('a', getattr(publisher.samples[0], "name"))

    def test_wildcard_excluded_counters(self):
        counter_cfg = ['*', '!a']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        pipe = pipeline_manager.pipelines[0]
        self.assertFalse(pipe.source.support_meter('a'))

    def test_wildcard_excluded_counters_not_excluded(self):
        counter_cfg = ['*', '!b']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        with pipeline_manager.publisher() as p:
            p([self.test_counter])
        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(1, len(publisher.samples))
        self.assertEqual('a', getattr(publisher.samples[0], "name"))

    def test_all_excluded_counters_not_excluded(self):
        counter_cfg = ['!b', '!c']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        with pipeline_manager.publisher() as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(1, len(publisher.samples))
        self.assertEqual('a', getattr(publisher.samples[0], "name"))

    def test_all_excluded_counters_is_excluded(self):
        counter_cfg = ['!a', '!c']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        pipe = pipeline_manager.pipelines[0]
        self.assertFalse(pipe.source.support_meter('a'))
        self.assertTrue(pipe.source.support_meter('b'))
        self.assertFalse(pipe.source.support_meter('c'))

    def test_wildcard_and_excluded_wildcard_counters(self):
        counter_cfg = ['*', '!disk.*']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        pipe = pipeline_manager.pipelines[0]
        self.assertFalse(pipe.source.support_meter('disk.read.bytes'))
        self.assertTrue(pipe.source.support_meter('cpu'))

    def test_included_counter_and_wildcard_counters(self):
        counter_cfg = ['cpu', 'disk.*']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        pipe = pipeline_manager.pipelines[0]
        self.assertTrue(pipe.source.support_meter('disk.read.bytes'))
        self.assertTrue(pipe.source.support_meter('cpu'))
        self.assertFalse(pipe.source.support_meter('instance'))

    def test_excluded_counter_and_excluded_wildcard_counters(self):
        counter_cfg = ['!cpu', '!disk.*']
        self._set_pipeline_cfg('meters', counter_cfg)
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        pipe = pipeline_manager.pipelines[0]
        self.assertFalse(pipe.source.support_meter('disk.read.bytes'))
        self.assertFalse(pipe.source.support_meter('cpu'))
        self.assertTrue(pipe.source.support_meter('instance'))

    def test_multiple_pipeline(self):
        self._augment_pipeline_cfg()
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        with pipeline_manager.publisher() as p:
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

        with pipeline_manager.publisher() as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(1, len(publisher.samples))
        self.assertEqual(1, publisher.calls)
        self.assertEqual('a', getattr(publisher.samples[0], "name"))
        new_publisher = pipeline_manager.pipelines[1].publishers[0]
        self.assertEqual(1, len(new_publisher.samples))
        self.assertEqual(1, new_publisher.calls)
        self.assertEqual('b', getattr(new_publisher.samples[0], "name"))

    def test_multiple_pipeline_exception(self):
        self._reraise_exception = False
        self._break_pipeline_cfg()
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)

        with pipeline_manager.publisher() as p:
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

        with pipeline_manager.publisher() as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(1, publisher.calls)
        self.assertEqual(1, len(publisher.samples))
        self.assertEqual('a', getattr(publisher.samples[0], "name"))

    def test_multiple_publisher(self):
        self._set_pipeline_cfg('publishers', ['test://', 'new://'])
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        with pipeline_manager.publisher() as p:
            p([self.test_counter])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        new_publisher = pipeline_manager.pipelines[0].publishers[1]
        self.assertEqual(1, len(publisher.samples))
        self.assertEqual(1, len(new_publisher.samples))
        self.assertEqual('a', getattr(new_publisher.samples[0], 'name'))
        self.assertEqual('a', getattr(publisher.samples[0], 'name'))

    def test_multiple_publisher_isolation(self):
        self._reraise_exception = False
        self._set_pipeline_cfg('publishers', ['except://', 'new://'])
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        with pipeline_manager.publisher() as p:
            p([self.test_counter])

        new_publisher = pipeline_manager.pipelines[0].publishers[1]
        self.assertEqual(1, len(new_publisher.samples))
        self.assertEqual('a', getattr(new_publisher.samples[0], 'name'))

    def test_multiple_counter_pipeline(self):
        self._set_pipeline_cfg('meters', ['a', 'b'])
        self._build_and_set_new_pipeline()
        pipeline_manager = pipeline.SamplePipelineManager(self.CONF)
        with pipeline_manager.publisher() as p:
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
        self.assertEqual(2, len(publisher.samples))
        self.assertEqual('a', getattr(publisher.samples[0], 'name'))
        self.assertEqual('b', getattr(publisher.samples[1], 'name'))

    def test_unique_pipeline_names(self):
        self._dup_pipeline_name_cfg()
        self._exception_create_pipelinemanager()
