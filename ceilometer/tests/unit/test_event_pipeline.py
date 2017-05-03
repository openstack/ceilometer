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
import traceback
import uuid

import fixtures
import mock
import oslo_messaging

from ceilometer.event.storage import models
from ceilometer import pipeline
from ceilometer import publisher
from ceilometer.publisher import test as test_publisher
from ceilometer.publisher import utils
from ceilometer import service
from ceilometer.tests import base


class EventPipelineTestCase(base.BaseTestCase):

    def get_publisher(self, conf, url, namespace=''):
        fake_drivers = {'test://': test_publisher.TestPublisher,
                        'new://': test_publisher.TestPublisher,
                        'except://': self.PublisherClassException}
        return fake_drivers[url](conf, url)

    class PublisherClassException(publisher.ConfigPublisherBase):
        def publish_samples(self, samples):
            pass

        def publish_events(self, events):
            raise Exception()

    def setUp(self):
        super(EventPipelineTestCase, self).setUp()
        self.CONF = service.prepare_service([], [])

        self.p_type = pipeline.EVENT_TYPE
        self.transformer_manager = None

        self.test_event = models.Event(
            message_id=uuid.uuid4(),
            event_type='a',
            generated=datetime.datetime.utcnow(),
            traits=[
                models.Trait('t_text', 1, 'text_trait'),
                models.Trait('t_int', 2, 'int_trait'),
                models.Trait('t_float', 3, 'float_trait'),
                models.Trait('t_datetime', 4, 'datetime_trait')
            ],
            raw={'status': 'started'}
        )

        self.test_event2 = models.Event(
            message_id=uuid.uuid4(),
            event_type='b',
            generated=datetime.datetime.utcnow(),
            traits=[
                models.Trait('t_text', 1, 'text_trait'),
                models.Trait('t_int', 2, 'int_trait'),
                models.Trait('t_float', 3, 'float_trait'),
                models.Trait('t_datetime', 4, 'datetime_trait')
            ],
            raw={'status': 'stopped'}
        )

        self.useFixture(fixtures.MockPatchObject(
            publisher, 'get_publisher', side_effect=self.get_publisher))

        self._setup_pipeline_cfg()

        self._reraise_exception = True
        self.useFixture(fixtures.MockPatch(
            'ceilometer.pipeline.LOG.exception',
            side_effect=self._handle_reraise_exception))

    def _handle_reraise_exception(self, *args, **kwargs):
        if self._reraise_exception:
            raise Exception(traceback.format_exc())

    def _setup_pipeline_cfg(self):
        """Setup the appropriate form of pipeline config."""
        source = {'name': 'test_source',
                  'events': ['a'],
                  'sinks': ['test_sink']}
        sink = {'name': 'test_sink',
                'publishers': ['test://']}
        self.pipeline_cfg = {'sources': [source], 'sinks': [sink]}

    def _augment_pipeline_cfg(self):
        """Augment the pipeline config with an additional element."""
        self.pipeline_cfg['sources'].append({
            'name': 'second_source',
            'events': ['b'],
            'sinks': ['second_sink']
        })
        self.pipeline_cfg['sinks'].append({
            'name': 'second_sink',
            'publishers': ['new://'],
        })

    def _break_pipeline_cfg(self):
        """Break the pipeline config with a malformed element."""
        self.pipeline_cfg['sources'].append({
            'name': 'second_source',
            'events': ['b'],
            'sinks': ['second_sink']
        })
        self.pipeline_cfg['sinks'].append({
            'name': 'second_sink',
            'publishers': ['except'],
        })

    def _dup_pipeline_name_cfg(self):
        """Break the pipeline config with duplicate pipeline name."""
        self.pipeline_cfg['sources'].append({
            'name': 'test_source',
            'events': ['a'],
            'sinks': ['test_sink']
        })

    def _set_pipeline_cfg(self, field, value):
        if field in self.pipeline_cfg['sources'][0]:
            self.pipeline_cfg['sources'][0][field] = value
        else:
            self.pipeline_cfg['sinks'][0][field] = value

    def _extend_pipeline_cfg(self, field, value):
        if field in self.pipeline_cfg['sources'][0]:
            self.pipeline_cfg['sources'][0][field].extend(value)
        else:
            self.pipeline_cfg['sinks'][0][field].extend(value)

    def _unset_pipeline_cfg(self, field):
        if field in self.pipeline_cfg['sources'][0]:
            del self.pipeline_cfg['sources'][0][field]
        else:
            del self.pipeline_cfg['sinks'][0][field]

    def _exception_create_pipelinemanager(self):
        self.assertRaises(pipeline.PipelineException,
                          pipeline.PipelineManager,
                          self.CONF,
                          self.cfg2file(self.pipeline_cfg),
                          self.transformer_manager,
                          self.p_type)

    def test_no_events(self):
        self._unset_pipeline_cfg('events')
        self._exception_create_pipelinemanager()

    def test_no_name(self):
        self._unset_pipeline_cfg('name')
        self._exception_create_pipelinemanager()

    def test_name(self):
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        for pipe in pipeline_manager.pipelines:
            self.assertTrue(pipe.name.startswith('event:'))

    def test_no_publishers(self):
        self._unset_pipeline_cfg('publishers')
        self._exception_create_pipelinemanager()

    def test_check_events_include_exclude_same(self):
        event_cfg = ['a', '!a']
        self._set_pipeline_cfg('events', event_cfg)
        self._exception_create_pipelinemanager()

    def test_check_events_include_exclude(self):
        event_cfg = ['a', '!b']
        self._set_pipeline_cfg('events', event_cfg)
        self._exception_create_pipelinemanager()

    def test_check_events_wildcard_included(self):
        event_cfg = ['a', '*']
        self._set_pipeline_cfg('events', event_cfg)
        self._exception_create_pipelinemanager()

    def test_check_publishers_invalid_publisher(self):
        publisher_cfg = ['test_invalid']
        self._set_pipeline_cfg('publishers', publisher_cfg)

    def test_multiple_included_events(self):
        event_cfg = ['a', 'b']
        self._set_pipeline_cfg('events', event_cfg)
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)

        with pipeline_manager.publisher() as p:
            p([self.test_event])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(1, len(publisher.events))

        with pipeline_manager.publisher() as p:
            p([self.test_event2])

        self.assertEqual(2, len(publisher.events))
        self.assertEqual('a', getattr(publisher.events[0], 'event_type'))
        self.assertEqual('b', getattr(publisher.events[1], 'event_type'))

    def test_event_non_match(self):
        event_cfg = ['nomatch']
        self._set_pipeline_cfg('events', event_cfg)
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        with pipeline_manager.publisher() as p:
            p([self.test_event])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(0, len(publisher.events))
        self.assertEqual(0, publisher.calls)

    def test_wildcard_event(self):
        event_cfg = ['*']
        self._set_pipeline_cfg('events', event_cfg)
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        with pipeline_manager.publisher() as p:
            p([self.test_event])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(1, len(publisher.events))
        self.assertEqual('a', getattr(publisher.events[0], 'event_type'))

    def test_wildcard_excluded_events(self):
        event_cfg = ['*', '!a']
        self._set_pipeline_cfg('events', event_cfg)
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        self.assertFalse(pipeline_manager.pipelines[0].support_event('a'))

    def test_wildcard_excluded_events_not_excluded(self):
        event_cfg = ['*', '!b']
        self._set_pipeline_cfg('events', event_cfg)
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        with pipeline_manager.publisher() as p:
            p([self.test_event])
        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(1, len(publisher.events))
        self.assertEqual('a', getattr(publisher.events[0], 'event_type'))

    def test_all_excluded_events_not_excluded(self):
        event_cfg = ['!b', '!c']
        self._set_pipeline_cfg('events', event_cfg)
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        with pipeline_manager.publisher() as p:
            p([self.test_event])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(1, len(publisher.events))
        self.assertEqual('a', getattr(publisher.events[0], 'event_type'))

    def test_all_excluded_events_excluded(self):
        event_cfg = ['!a', '!c']
        self._set_pipeline_cfg('events', event_cfg)
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        self.assertFalse(pipeline_manager.pipelines[0].support_event('a'))
        self.assertTrue(pipeline_manager.pipelines[0].support_event('b'))
        self.assertFalse(pipeline_manager.pipelines[0].support_event('c'))

    def test_wildcard_and_excluded_wildcard_events(self):
        event_cfg = ['*', '!compute.*']
        self._set_pipeline_cfg('events', event_cfg)
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        self.assertFalse(pipeline_manager.pipelines[0].
                         support_event('compute.instance.create.start'))
        self.assertTrue(pipeline_manager.pipelines[0].
                        support_event('identity.user.create'))

    def test_included_event_and_wildcard_events(self):
        event_cfg = ['compute.instance.create.start', 'identity.*']
        self._set_pipeline_cfg('events', event_cfg)
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        self.assertTrue(pipeline_manager.pipelines[0].
                        support_event('identity.user.create'))
        self.assertTrue(pipeline_manager.pipelines[0].
                        support_event('compute.instance.create.start'))
        self.assertFalse(pipeline_manager.pipelines[0].
                         support_event('compute.instance.create.stop'))

    def test_excluded_event_and_excluded_wildcard_events(self):
        event_cfg = ['!compute.instance.create.start', '!identity.*']
        self._set_pipeline_cfg('events', event_cfg)
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        self.assertFalse(pipeline_manager.pipelines[0].
                         support_event('identity.user.create'))
        self.assertFalse(pipeline_manager.pipelines[0].
                         support_event('compute.instance.create.start'))
        self.assertTrue(pipeline_manager.pipelines[0].
                        support_event('compute.instance.create.stop'))

    def test_multiple_pipeline(self):
        self._augment_pipeline_cfg()

        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        with pipeline_manager.publisher() as p:
            p([self.test_event, self.test_event2])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(1, len(publisher.events))
        self.assertEqual(1, publisher.calls)
        self.assertEqual('a', getattr(publisher.events[0], 'event_type'))
        new_publisher = pipeline_manager.pipelines[1].publishers[0]
        self.assertEqual(1, len(new_publisher.events))
        self.assertEqual(1, new_publisher.calls)
        self.assertEqual('b', getattr(new_publisher.events[0], 'event_type'))

    def test_multiple_publisher(self):
        self._set_pipeline_cfg('publishers', ['test://', 'new://'])
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)

        with pipeline_manager.publisher() as p:
            p([self.test_event])

        publisher = pipeline_manager.pipelines[0].publishers[0]
        new_publisher = pipeline_manager.pipelines[0].publishers[1]
        self.assertEqual(1, len(publisher.events))
        self.assertEqual(1, len(new_publisher.events))
        self.assertEqual('a', getattr(new_publisher.events[0], 'event_type'))
        self.assertEqual('a', getattr(publisher.events[0], 'event_type'))

    def test_multiple_publisher_isolation(self):
        self._reraise_exception = False
        self._set_pipeline_cfg('publishers', ['except://', 'new://'])
        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        with pipeline_manager.publisher() as p:
            p([self.test_event])

        publisher = pipeline_manager.pipelines[0].publishers[1]
        self.assertEqual(1, len(publisher.events))
        self.assertEqual('a', getattr(publisher.events[0], 'event_type'))

    def test_unique_pipeline_names(self):
        self._dup_pipeline_name_cfg()
        self._exception_create_pipelinemanager()

    def test_event_pipeline_endpoint_requeue_on_failure(self):

        self.CONF.set_override("ack_on_event_error", False,
                               group="notification")
        self.CONF.set_override("telemetry_secret", "not-so-secret",
                               group="publisher")
        test_data = {
            'message_id': uuid.uuid4(),
            'event_type': 'a',
            'generated': '2013-08-08 21:06:37.803826',
            'traits': [
                {'name': 't_text',
                 'value': 1,
                 'dtype': 'text_trait'
                 }
            ],
            'raw': {'status': 'started'}
        }
        message_sign = utils.compute_signature(test_data, 'not-so-secret')
        test_data['message_signature'] = message_sign

        fake_publisher = mock.Mock()
        self.useFixture(fixtures.MockPatch(
            'ceilometer.publisher.test.TestPublisher',
            return_value=fake_publisher))

        pipeline_manager = pipeline.PipelineManager(
            self.CONF,
            self.cfg2file(self.pipeline_cfg),
            self.transformer_manager,
            self.p_type)
        event_pipeline_endpoint = pipeline.EventPipelineEndpoint(
            pipeline_manager.pipelines[0])

        fake_publisher.publish_events.side_effect = Exception
        ret = event_pipeline_endpoint.sample([
            {'ctxt': {}, 'publisher_id': 'compute.vagrant-precise',
             'event_type': 'a', 'payload': [test_data], 'metadata': {}}])
        self.assertEqual(oslo_messaging.NotificationResult.REQUEUE, ret)
