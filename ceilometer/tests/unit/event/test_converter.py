#
# Copyright 2013 Rackspace Hosting.
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

import jsonpath_rw_ext
import mock
import six

from ceilometer import declarative
from ceilometer.event import converter
from ceilometer.event.storage import models
from ceilometer import service as ceilometer_service
from ceilometer.tests import base


class ConverterBase(base.BaseTestCase):
    @staticmethod
    def _create_test_notification(event_type, message_id, **kw):
        return dict(event_type=event_type,
                    metadata=dict(message_id=message_id,
                                  timestamp="2013-08-08 21:06:37.803826"),
                    publisher_id="compute.host-1-2-3",
                    payload=kw,
                    )

    def assertIsValidEvent(self, event, notification):
        self.assertIsNot(
            None, event,
            "Notification dropped unexpectedly:"
            " %s" % str(notification))
        self.assertIsInstance(event, models.Event)

    def assertIsNotValidEvent(self, event, notification):
        self.assertIs(
            None, event,
            "Notification NOT dropped when expected to be dropped:"
            " %s" % str(notification))

    def assertHasTrait(self, event, name, value=None, dtype=None):
        traits = [trait for trait in event.traits if trait.name == name]
        self.assertGreater(len(traits), 0,
                           "Trait %s not found in event %s" % (name, event))
        trait = traits[0]
        if value is not None:
            self.assertEqual(value, trait.value)
        if dtype is not None:
            self.assertEqual(dtype, trait.dtype)
            if dtype == models.Trait.INT_TYPE:
                self.assertIsInstance(trait.value, int)
            elif dtype == models.Trait.FLOAT_TYPE:
                self.assertIsInstance(trait.value, float)
            elif dtype == models.Trait.DATETIME_TYPE:
                self.assertIsInstance(trait.value, datetime.datetime)
            elif dtype == models.Trait.TEXT_TYPE:
                self.assertIsInstance(trait.value, six.string_types)

    def assertDoesNotHaveTrait(self, event, name):
        traits = [trait for trait in event.traits if trait.name == name]
        self.assertEqual(
            len(traits), 0,
            "Extra Trait %s found in event %s" % (name, event))

    def assertHasDefaultTraits(self, event):
        text = models.Trait.TEXT_TYPE
        self.assertHasTrait(event, 'service', dtype=text)

    def _cmp_tree(self, this, other):
        if hasattr(this, 'right') and hasattr(other, 'right'):
            return (self._cmp_tree(this.right, other.right) and
                    self._cmp_tree(this.left, other.left))
        if not hasattr(this, 'right') and not hasattr(other, 'right'):
            return this == other
        return False

    def assertPathsEqual(self, path1, path2):
        self.assertTrue(self._cmp_tree(path1, path2),
                        'JSONPaths not equivalent %s %s' % (path1, path2))


class TestTraitDefinition(ConverterBase):

    def setUp(self):
        super(TestTraitDefinition, self).setUp()
        self.n1 = self._create_test_notification(
            "test.thing",
            "uuid-for-notif-0001",
            instance_uuid="uuid-for-instance-0001",
            instance_id="id-for-instance-0001",
            instance_uuid2=None,
            instance_id2=None,
            host='host-1-2-3',
            bogus_date='',
            image_meta=dict(
                        disk_gb='20',
                        thing='whatzit'),
            foobar=50)

        self.ext1 = mock.MagicMock(name='mock_test_plugin')
        self.test_plugin_class = self.ext1.plugin
        self.test_plugin = self.test_plugin_class()
        self.test_plugin.trait_values.return_value = ['foobar']
        self.ext1.reset_mock()

        self.ext2 = mock.MagicMock(name='mock_nothing_plugin')
        self.nothing_plugin_class = self.ext2.plugin
        self.nothing_plugin = self.nothing_plugin_class()
        self.nothing_plugin.trait_values.return_value = [None]
        self.ext2.reset_mock()

        self.fake_plugin_mgr = dict(test=self.ext1, nothing=self.ext2)

    def test_to_trait_with_plugin(self):
        cfg = dict(type='text',
                   fields=['payload.instance_id', 'payload.instance_uuid'],
                   plugin=dict(name='test'))

        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsInstance(t, models.Trait)
        self.assertEqual('test_trait', t.name)
        self.assertEqual(models.Trait.TEXT_TYPE, t.dtype)
        self.assertEqual('foobar', t.value)
        self.test_plugin_class.assert_called_once_with()
        self.test_plugin.trait_values.assert_called_once_with([
            ('payload.instance_id', 'id-for-instance-0001'),
            ('payload.instance_uuid', 'uuid-for-instance-0001')])

    def test_to_trait_null_match_with_plugin(self):
        cfg = dict(type='text',
                   fields=['payload.nothere', 'payload.bogus'],
                   plugin=dict(name='test'))

        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsInstance(t, models.Trait)
        self.assertEqual('test_trait', t.name)
        self.assertEqual(models.Trait.TEXT_TYPE, t.dtype)
        self.assertEqual('foobar', t.value)
        self.test_plugin_class.assert_called_once_with()
        self.test_plugin.trait_values.assert_called_once_with([])

    def test_to_trait_with_plugin_null(self):
        cfg = dict(type='text',
                   fields=['payload.instance_id', 'payload.instance_uuid'],
                   plugin=dict(name='nothing'))

        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsNone(t)
        self.nothing_plugin_class.assert_called_once_with()
        self.nothing_plugin.trait_values.assert_called_once_with([
            ('payload.instance_id', 'id-for-instance-0001'),
            ('payload.instance_uuid', 'uuid-for-instance-0001')])

    def test_to_trait_with_plugin_with_parameters(self):
        cfg = dict(type='text',
                   fields=['payload.instance_id', 'payload.instance_uuid'],
                   plugin=dict(name='test', parameters=dict(a=1, b='foo')))

        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsInstance(t, models.Trait)
        self.assertEqual('test_trait', t.name)
        self.assertEqual(models.Trait.TEXT_TYPE, t.dtype)
        self.assertEqual('foobar', t.value)
        self.test_plugin_class.assert_called_once_with(a=1, b='foo')
        self.test_plugin.trait_values.assert_called_once_with([
            ('payload.instance_id', 'id-for-instance-0001'),
            ('payload.instance_uuid', 'uuid-for-instance-0001')])

    def test_to_trait(self):
        cfg = dict(type='text', fields='payload.instance_id')
        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsInstance(t, models.Trait)
        self.assertEqual('test_trait', t.name)
        self.assertEqual(models.Trait.TEXT_TYPE, t.dtype)
        self.assertEqual('id-for-instance-0001', t.value)

        cfg = dict(type='int', fields='payload.image_meta.disk_gb')
        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsInstance(t, models.Trait)
        self.assertEqual('test_trait', t.name)
        self.assertEqual(models.Trait.INT_TYPE, t.dtype)
        self.assertEqual(20, t.value)

    def test_to_trait_multiple(self):
        cfg = dict(type='text', fields=['payload.instance_id',
                                        'payload.instance_uuid'])
        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsInstance(t, models.Trait)
        self.assertEqual('id-for-instance-0001', t.value)

        cfg = dict(type='text', fields=['payload.instance_uuid',
                                        'payload.instance_id'])
        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsInstance(t, models.Trait)
        self.assertEqual('uuid-for-instance-0001', t.value)

    def test_to_trait_multiple_different_nesting(self):
        cfg = dict(type='int', fields=['payload.foobar',
                   'payload.image_meta.disk_gb'])
        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsInstance(t, models.Trait)
        self.assertEqual(50, t.value)

        cfg = dict(type='int', fields=['payload.image_meta.disk_gb',
                   'payload.foobar'])
        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsInstance(t, models.Trait)
        self.assertEqual(20, t.value)

    def test_to_trait_some_null_multiple(self):
        cfg = dict(type='text', fields=['payload.instance_id2',
                                        'payload.instance_uuid'])
        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsInstance(t, models.Trait)
        self.assertEqual('uuid-for-instance-0001', t.value)

    def test_to_trait_some_missing_multiple(self):
        cfg = dict(type='text', fields=['payload.not_here_boss',
                                        'payload.instance_uuid'])
        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsInstance(t, models.Trait)
        self.assertEqual('uuid-for-instance-0001', t.value)

    def test_to_trait_missing(self):
        cfg = dict(type='text', fields='payload.not_here_boss')
        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsNone(t)

    def test_to_trait_null(self):
        cfg = dict(type='text', fields='payload.instance_id2')
        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsNone(t)

    def test_to_trait_empty_nontext(self):
        cfg = dict(type='datetime', fields='payload.bogus_date')
        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsNone(t)

    def test_to_trait_multiple_null_missing(self):
        cfg = dict(type='text', fields=['payload.not_here_boss',
                                        'payload.instance_id2'])
        tdef = converter.TraitDefinition('test_trait', cfg,
                                         self.fake_plugin_mgr)
        t = tdef.to_trait(self.n1)
        self.assertIsNone(t)

    def test_missing_fields_config(self):
        self.assertRaises(declarative.DefinitionException,
                          converter.TraitDefinition,
                          'bogus_trait',
                          dict(),
                          self.fake_plugin_mgr)

    def test_string_fields_config(self):
        cfg = dict(fields='payload.test')
        t = converter.TraitDefinition('test_trait', cfg, self.fake_plugin_mgr)
        self.assertPathsEqual(t.getter.__self__,
                              jsonpath_rw_ext.parse('payload.test'))

    def test_list_fields_config(self):
        cfg = dict(fields=['payload.test', 'payload.other'])
        t = converter.TraitDefinition('test_trait', cfg, self.fake_plugin_mgr)
        self.assertPathsEqual(
            t.getter.__self__,
            jsonpath_rw_ext.parse('(payload.test)|(payload.other)'))

    def test_invalid_path_config(self):
        # test invalid jsonpath...
        cfg = dict(fields='payload.bogus(')
        self.assertRaises(declarative.DefinitionException,
                          converter.TraitDefinition,
                          'bogus_trait',
                          cfg,
                          self.fake_plugin_mgr)

    def test_invalid_plugin_config(self):
        # test invalid jsonpath...
        cfg = dict(fields='payload.test', plugin=dict(bogus="true"))
        self.assertRaises(declarative.DefinitionException,
                          converter.TraitDefinition,
                          'test_trait',
                          cfg,
                          self.fake_plugin_mgr)

    def test_unknown_plugin(self):
        # test invalid jsonpath...
        cfg = dict(fields='payload.test', plugin=dict(name='bogus'))
        self.assertRaises(declarative.DefinitionException,
                          converter.TraitDefinition,
                          'test_trait',
                          cfg,
                          self.fake_plugin_mgr)

    def test_type_config(self):
        cfg = dict(type='text', fields='payload.test')
        t = converter.TraitDefinition('test_trait', cfg, self.fake_plugin_mgr)
        self.assertEqual(models.Trait.TEXT_TYPE, t.trait_type)

        cfg = dict(type='int', fields='payload.test')
        t = converter.TraitDefinition('test_trait', cfg, self.fake_plugin_mgr)
        self.assertEqual(models.Trait.INT_TYPE, t.trait_type)

        cfg = dict(type='float', fields='payload.test')
        t = converter.TraitDefinition('test_trait', cfg, self.fake_plugin_mgr)
        self.assertEqual(models.Trait.FLOAT_TYPE, t.trait_type)

        cfg = dict(type='datetime', fields='payload.test')
        t = converter.TraitDefinition('test_trait', cfg, self.fake_plugin_mgr)
        self.assertEqual(models.Trait.DATETIME_TYPE, t.trait_type)

    def test_invalid_type_config(self):
        # test invalid jsonpath...
        cfg = dict(type='bogus', fields='payload.test')
        self.assertRaises(declarative.DefinitionException,
                          converter.TraitDefinition,
                          'bogus_trait',
                          cfg,
                          self.fake_plugin_mgr)


class TestEventDefinition(ConverterBase):

    def setUp(self):
        super(TestEventDefinition, self).setUp()

        self.traits_cfg = {
            'instance_id': {
                'type': 'text',
                'fields': ['payload.instance_uuid',
                           'payload.instance_id'],
            },
            'host': {
                'type': 'text',
                'fields': 'payload.host',
            },
        }

        self.test_notification1 = self._create_test_notification(
            "test.thing",
            "uuid-for-notif-0001",
            instance_id="uuid-for-instance-0001",
            host='host-1-2-3')

        self.test_notification2 = self._create_test_notification(
            "test.thing",
            "uuid-for-notif-0002",
            instance_id="uuid-for-instance-0002")

        self.test_notification3 = self._create_test_notification(
            "test.thing",
            "uuid-for-notif-0003",
            instance_id="uuid-for-instance-0003",
            host=None)
        self.fake_plugin_mgr = {}

    def test_to_event(self):
        dtype = models.Trait.TEXT_TYPE
        cfg = dict(event_type='test.thing', traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])

        e = edef.to_event('INFO', self.test_notification1)
        self.assertEqual('test.thing', e.event_type)
        self.assertEqual(datetime.datetime(2013, 8, 8, 21, 6, 37, 803826),
                         e.generated)

        self.assertHasDefaultTraits(e)
        self.assertHasTrait(e, 'host', value='host-1-2-3', dtype=dtype)
        self.assertHasTrait(e, 'instance_id',
                            value='uuid-for-instance-0001',
                            dtype=dtype)

    def test_to_event_missing_trait(self):
        dtype = models.Trait.TEXT_TYPE
        cfg = dict(event_type='test.thing', traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])

        e = edef.to_event('INFO', self.test_notification2)

        self.assertHasDefaultTraits(e)
        self.assertHasTrait(e, 'instance_id',
                            value='uuid-for-instance-0002',
                            dtype=dtype)
        self.assertDoesNotHaveTrait(e, 'host')

    def test_to_event_null_trait(self):
        dtype = models.Trait.TEXT_TYPE
        cfg = dict(event_type='test.thing', traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])

        e = edef.to_event('INFO', self.test_notification3)

        self.assertHasDefaultTraits(e)
        self.assertHasTrait(e, 'instance_id',
                            value='uuid-for-instance-0003',
                            dtype=dtype)
        self.assertDoesNotHaveTrait(e, 'host')

    def test_bogus_cfg_no_traits(self):
        bogus = dict(event_type='test.foo')
        self.assertRaises(declarative.DefinitionException,
                          converter.EventDefinition,
                          bogus,
                          self.fake_plugin_mgr,
                          [])

    def test_bogus_cfg_no_type(self):
        bogus = dict(traits=self.traits_cfg)
        self.assertRaises(declarative.DefinitionException,
                          converter.EventDefinition,
                          bogus,
                          self.fake_plugin_mgr,
                          [])

    def test_included_type_string(self):
        cfg = dict(event_type='test.thing', traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        self.assertEqual(1, len(edef._included_types))
        self.assertEqual('test.thing', edef._included_types[0])
        self.assertEqual(0, len(edef._excluded_types))
        self.assertTrue(edef.included_type('test.thing'))
        self.assertFalse(edef.excluded_type('test.thing'))
        self.assertTrue(edef.match_type('test.thing'))
        self.assertFalse(edef.match_type('random.thing'))

    def test_included_type_list(self):
        cfg = dict(event_type=['test.thing', 'other.thing'],
                   traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        self.assertEqual(2, len(edef._included_types))
        self.assertEqual(0, len(edef._excluded_types))
        self.assertTrue(edef.included_type('test.thing'))
        self.assertTrue(edef.included_type('other.thing'))
        self.assertFalse(edef.excluded_type('test.thing'))
        self.assertTrue(edef.match_type('test.thing'))
        self.assertTrue(edef.match_type('other.thing'))
        self.assertFalse(edef.match_type('random.thing'))

    def test_excluded_type_string(self):
        cfg = dict(event_type='!test.thing', traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        self.assertEqual(1, len(edef._included_types))
        self.assertEqual('*', edef._included_types[0])
        self.assertEqual('test.thing', edef._excluded_types[0])
        self.assertEqual(1, len(edef._excluded_types))
        self.assertEqual('test.thing', edef._excluded_types[0])
        self.assertTrue(edef.excluded_type('test.thing'))
        self.assertTrue(edef.included_type('random.thing'))
        self.assertFalse(edef.match_type('test.thing'))
        self.assertTrue(edef.match_type('random.thing'))

    def test_excluded_type_list(self):
        cfg = dict(event_type=['!test.thing', '!other.thing'],
                   traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        self.assertEqual(1, len(edef._included_types))
        self.assertEqual(2, len(edef._excluded_types))
        self.assertTrue(edef.excluded_type('test.thing'))
        self.assertTrue(edef.excluded_type('other.thing'))
        self.assertFalse(edef.excluded_type('random.thing'))
        self.assertFalse(edef.match_type('test.thing'))
        self.assertFalse(edef.match_type('other.thing'))
        self.assertTrue(edef.match_type('random.thing'))

    def test_mixed_type_list(self):
        cfg = dict(event_type=['*.thing', '!test.thing', '!other.thing'],
                   traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        self.assertEqual(1, len(edef._included_types))
        self.assertEqual(2, len(edef._excluded_types))
        self.assertTrue(edef.excluded_type('test.thing'))
        self.assertTrue(edef.excluded_type('other.thing'))
        self.assertFalse(edef.excluded_type('random.thing'))
        self.assertFalse(edef.match_type('test.thing'))
        self.assertFalse(edef.match_type('other.thing'))
        self.assertFalse(edef.match_type('random.whatzit'))
        self.assertTrue(edef.match_type('random.thing'))

    def test_catchall(self):
        cfg = dict(event_type=['*.thing', '!test.thing', '!other.thing'],
                   traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        self.assertFalse(edef.is_catchall)

        cfg = dict(event_type=['!other.thing'],
                   traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        self.assertFalse(edef.is_catchall)

        cfg = dict(event_type=['other.thing'],
                   traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        self.assertFalse(edef.is_catchall)

        cfg = dict(event_type=['*', '!other.thing'],
                   traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        self.assertFalse(edef.is_catchall)

        cfg = dict(event_type=['*'],
                   traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        self.assertTrue(edef.is_catchall)

        cfg = dict(event_type=['*', 'foo'],
                   traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        self.assertTrue(edef.is_catchall)

    def test_default_traits(self):
        cfg = dict(event_type='test.thing', traits={})
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        default_traits = converter.EventDefinition.DEFAULT_TRAITS.keys()
        traits = set(edef.traits.keys())
        for dt in default_traits:
            self.assertIn(dt, traits)
        self.assertEqual(len(converter.EventDefinition.DEFAULT_TRAITS),
                         len(edef.traits))

    def test_traits(self):
        cfg = dict(event_type='test.thing', traits=self.traits_cfg)
        edef = converter.EventDefinition(cfg, self.fake_plugin_mgr, [])
        default_traits = converter.EventDefinition.DEFAULT_TRAITS.keys()
        traits = set(edef.traits.keys())
        for dt in default_traits:
            self.assertIn(dt, traits)
        self.assertIn('host', traits)
        self.assertIn('instance_id', traits)
        self.assertEqual(len(converter.EventDefinition.DEFAULT_TRAITS) + 2,
                         len(edef.traits))


class TestNotificationConverter(ConverterBase):

    def setUp(self):
        super(TestNotificationConverter, self).setUp()
        self.CONF = ceilometer_service.prepare_service([], [])
        self.valid_event_def1 = [{
            'event_type': 'compute.instance.create.*',
            'traits': {
                'instance_id': {
                    'type': 'text',
                    'fields': ['payload.instance_uuid',
                               'payload.instance_id'],
                },
                'host': {
                    'type': 'text',
                    'fields': 'payload.host',
                },
            },
        }]

        self.test_notification1 = self._create_test_notification(
            "compute.instance.create.start",
            "uuid-for-notif-0001",
            instance_id="uuid-for-instance-0001",
            host='host-1-2-3')
        self.test_notification2 = self._create_test_notification(
            "bogus.notification.from.mars",
            "uuid-for-notif-0002",
            weird='true',
            host='cydonia')
        self.fake_plugin_mgr = {}

    @mock.patch('oslo_utils.timeutils.utcnow')
    def test_converter_missing_keys(self, mock_utcnow):
        self.CONF.set_override('drop_unmatched_notifications', False,
                               group='event')
        # test a malformed notification
        now = datetime.datetime.utcnow()
        mock_utcnow.return_value = now
        c = converter.NotificationEventsConverter(
            self.CONF, [], self.fake_plugin_mgr)
        message = {'event_type': "foo",
                   'metadata': {'message_id': "abc",
                                'timestamp': str(now)},
                   'publisher_id': "1"}
        e = c.to_event('INFO', message)
        self.assertIsValidEvent(e, message)
        self.assertEqual(1, len(e.traits))
        self.assertEqual("foo", e.event_type)
        self.assertEqual(now, e.generated)

    def test_converter_with_catchall(self):
        self.CONF.set_override('drop_unmatched_notifications', False,
                               group='event')
        c = converter.NotificationEventsConverter(
            self.CONF, self.valid_event_def1, self.fake_plugin_mgr)
        self.assertEqual(2, len(c.definitions))
        e = c.to_event('INFO', self.test_notification1)
        self.assertIsValidEvent(e, self.test_notification1)
        self.assertEqual(3, len(e.traits))
        self.assertHasDefaultTraits(e)
        self.assertHasTrait(e, 'instance_id')
        self.assertHasTrait(e, 'host')

        e = c.to_event('INFO', self.test_notification2)
        self.assertIsValidEvent(e, self.test_notification2)
        self.assertEqual(1, len(e.traits))
        self.assertHasDefaultTraits(e)
        self.assertDoesNotHaveTrait(e, 'instance_id')
        self.assertDoesNotHaveTrait(e, 'host')

    def test_converter_without_catchall(self):
        self.CONF.set_override('drop_unmatched_notifications', True,
                               group='event')
        c = converter.NotificationEventsConverter(
            self.CONF, self.valid_event_def1, self.fake_plugin_mgr)
        self.assertEqual(1, len(c.definitions))
        e = c.to_event('INFO', self.test_notification1)
        self.assertIsValidEvent(e, self.test_notification1)
        self.assertEqual(3, len(e.traits))
        self.assertHasDefaultTraits(e)
        self.assertHasTrait(e, 'instance_id')
        self.assertHasTrait(e, 'host')

        e = c.to_event('INFO', self.test_notification2)
        self.assertIsNotValidEvent(e, self.test_notification2)

    def test_converter_empty_cfg_with_catchall(self):
        self.CONF.set_override('drop_unmatched_notifications', False,
                               group='event')
        c = converter.NotificationEventsConverter(
            self.CONF, [], self.fake_plugin_mgr)
        self.assertEqual(1, len(c.definitions))
        e = c.to_event('INFO', self.test_notification1)
        self.assertIsValidEvent(e, self.test_notification1)
        self.assertEqual(1, len(e.traits))
        self.assertHasDefaultTraits(e)

        e = c.to_event('INFO', self.test_notification2)
        self.assertIsValidEvent(e, self.test_notification2)
        self.assertEqual(1, len(e.traits))
        self.assertHasDefaultTraits(e)

    def test_converter_empty_cfg_without_catchall(self):
        self.CONF.set_override('drop_unmatched_notifications', True,
                               group='event')
        c = converter.NotificationEventsConverter(
            self.CONF, [], self.fake_plugin_mgr)
        self.assertEqual(0, len(c.definitions))
        e = c.to_event('INFO', self.test_notification1)
        self.assertIsNotValidEvent(e, self.test_notification1)

        e = c.to_event('INFO', self.test_notification2)
        self.assertIsNotValidEvent(e, self.test_notification2)

    @staticmethod
    def _convert_message(convert, level):
        message = {'priority': level, 'event_type': "foo", 'publisher_id': "1",
                   'metadata': {'message_id': "abc",
                                'timestamp': "2013-08-08 21:06:37.803826"}}
        return convert.to_event(level, message)

    def test_store_raw_all(self):
        self.CONF.set_override('store_raw', ['info', 'error'],
                               group='event')
        c = converter.NotificationEventsConverter(
            self.CONF, [], self.fake_plugin_mgr)
        self.assertTrue(self._convert_message(c, 'info').raw)
        self.assertTrue(self._convert_message(c, 'error').raw)

    def test_store_raw_info_only(self):
        self.CONF.set_override('store_raw', ['info'],
                               group='event')
        c = converter.NotificationEventsConverter(
            self.CONF, [], self.fake_plugin_mgr)
        self.assertTrue(self._convert_message(c, 'info').raw)
        self.assertFalse(self._convert_message(c, 'error').raw)

    def test_store_raw_error_only(self):
        self.CONF.set_override('store_raw', ['error'],
                               group='event')
        c = converter.NotificationEventsConverter(
            self.CONF, [], self.fake_plugin_mgr)
        self.assertFalse(self._convert_message(c, 'info').raw)
        self.assertTrue(self._convert_message(c, 'error').raw)

    def test_store_raw_skip_all(self):
        c = converter.NotificationEventsConverter(
            self.CONF, [], self.fake_plugin_mgr)
        self.assertFalse(self._convert_message(c, 'info').raw)
        self.assertFalse(self._convert_message(c, 'error').raw)

    def test_store_raw_info_only_no_case(self):
        self.CONF.set_override('store_raw', ['INFO'],
                               group='event')
        c = converter.NotificationEventsConverter(
            self.CONF, [], self.fake_plugin_mgr)
        self.assertTrue(self._convert_message(c, 'info').raw)
        self.assertFalse(self._convert_message(c, 'error').raw)

    def test_store_raw_bad_skip_all(self):
        self.CONF.set_override('store_raw', ['unknown'],
                               group='event')
        c = converter.NotificationEventsConverter(
            self.CONF, [], self.fake_plugin_mgr)
        self.assertFalse(self._convert_message(c, 'info').raw)
        self.assertFalse(self._convert_message(c, 'error').raw)

    def test_store_raw_bad_and_good(self):
        self.CONF.set_override('store_raw', ['info', 'unknown'],
                               group='event')
        c = converter.NotificationEventsConverter(
            self.CONF, [], self.fake_plugin_mgr)
        self.assertTrue(self._convert_message(c, 'info').raw)
        self.assertFalse(self._convert_message(c, 'error').raw)

    @mock.patch('ceilometer.declarative.LOG')
    def test_setup_events_load_config_in_code_tree(self, mocked_log):
        self.CONF.set_override('definitions_cfg_file',
                               '/not/existing/file', group='event')
        self.CONF.set_override('drop_unmatched_notifications',
                               False, group='event')

        c = converter.setup_events(self.CONF, self.fake_plugin_mgr)
        self.assertIsInstance(c, converter.NotificationEventsConverter)
        log_called_args = mocked_log.debug.call_args_list
        self.assertEqual(
            'No Definitions configuration file found! Using default config.',
            log_called_args[0][0][0])
        self.assertTrue(log_called_args[1][0][0].startswith(
            'Loading definitions configuration file:'))
