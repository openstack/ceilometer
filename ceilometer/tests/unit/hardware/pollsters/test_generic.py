#
# Copyright 2015 Intel Corp.
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

import mock
import six
import yaml

import fixtures
from oslo_utils import fileutils

from ceilometer import declarative
from ceilometer.hardware.inspector import base as inspector_base
from ceilometer.hardware.pollsters import generic
from ceilometer import sample
from ceilometer import service
from ceilometer.tests import base as test_base


class TestMeterDefinition(test_base.BaseTestCase):
    def test_config_definition(self):
        cfg = dict(name='test',
                   type='gauge',
                   unit='B',
                   snmp_inspector={})
        definition = generic.MeterDefinition(cfg)
        self.assertEqual('test', definition.name)
        self.assertEqual('gauge', definition.type)
        self.assertEqual('B', definition.unit)
        self.assertEqual({}, definition.snmp_inspector)

    def test_config_missing_field(self):
        cfg = dict(name='test', type='gauge')
        try:
            generic.MeterDefinition(cfg)
        except declarative.MeterDefinitionException as e:
            self.assertEqual("Missing field unit", e.brief_message)

    def test_config_invalid_field(self):
        cfg = dict(name='test',
                   type='gauge',
                   unit='B',
                   invalid={})
        definition = generic.MeterDefinition(cfg)
        self.assertEqual("foobar", getattr(definition, 'invalid', 'foobar'))

    def test_config_invalid_type_field(self):
        cfg = dict(name='test',
                   type='invalid',
                   unit='B',
                   snmp_inspector={})
        try:
            generic.MeterDefinition(cfg)
        except declarative.MeterDefinitionException as e:
            self.assertEqual("Unrecognized type value invalid",
                             e.brief_message)

    @mock.patch('ceilometer.hardware.pollsters.generic.LOG')
    def test_bad_metric_skip(self, LOG):
        cfg = {'metric': [dict(name='test1',
                               type='gauge',
                               unit='B',
                               snmp_inspector={}),
                          dict(name='test_bad',
                               type='invalid',
                               unit='B',
                               snmp_inspector={}),
                          dict(name='test2',
                               type='gauge',
                               unit='B',
                               snmp_inspector={})]}
        data = generic.load_definition(cfg)
        self.assertEqual(2, len(data))
        LOG.error.assert_called_with(
            "Error loading meter definition: %s",
            "Unrecognized type value invalid")


class FakeInspector(inspector_base.Inspector):
    net_metadata = dict(name='test.teest',
                        mac='001122334455',
                        ip='10.0.0.2',
                        speed=1000)
    DATA = {
        'test': (0.99, {}, {}),
        'test2': (90, net_metadata, {}),
    }

    def inspect_generic(self, host, cache,
                        extra_metadata=None, param=None):
        yield self.DATA[host.hostname]


class TestGenericPollsters(test_base.BaseTestCase):
    @staticmethod
    def faux_get_inspector(url, namespace=None):
        return FakeInspector()

    def setUp(self):
        super(TestGenericPollsters, self).setUp()
        self.conf = service.prepare_service([], [])
        self.resources = ["snmp://test", "snmp://test2"]
        self.useFixture(fixtures.MockPatch(
            'ceilometer.hardware.inspector.get_inspector',
            self.faux_get_inspector))
        self.pollster = generic.GenericHardwareDeclarativePollster(self.conf)

    def _setup_meter_def_file(self, cfg):
        if six.PY3:
            cfg = cfg.encode('utf-8')
        meter_cfg_file = fileutils.write_to_tempfile(content=cfg,
                                                     prefix="snmp",
                                                     suffix="yaml")
        self.conf.set_override(
            'meter_definitions_file',
            meter_cfg_file, group='hardware')
        cfg = declarative.load_definitions(
            self.conf, {}, self.conf.hardware.meter_definitions_file)
        return cfg

    def _check_get_samples(self, name, definition,
                           expected_value, expected_type, expected_unit=None):
        self.pollster._update_meter_definition(definition)
        cache = {}
        samples = list(self.pollster.get_samples(None, cache,
                                                 self.resources))
        self.assertTrue(samples)
        self.assertIn(self.pollster.CACHE_KEY, cache)
        for resource in self.resources:
            self.assertIn(resource, cache[self.pollster.CACHE_KEY])

        self.assertEqual(set([name]),
                         set([s.name for s in samples]))
        match = [s for s in samples if s.name == name]
        self.assertEqual(expected_value, match[0].volume)
        self.assertEqual(expected_type, match[0].type)
        if expected_unit:
            self.assertEqual(expected_unit, match[0].unit)

    def test_get_samples(self):
        param = dict(matching_type='type_exact',
                     oid='1.3.6.1.4.1.2021.10.1.3.1',
                     type='lambda x: float(str(x))')
        meter_def = generic.MeterDefinition(dict(type='gauge',
                                                 name='hardware.test1',
                                                 unit='process',
                                                 snmp_inspector=param))
        self._check_get_samples('hardware.test1',
                                meter_def,
                                0.99, sample.TYPE_GAUGE,
                                expected_unit='process')

    def test_get_pollsters_extensions(self):
        param = dict(matching_type='type_exact',
                     oid='1.3.6.1.4.1.2021.10.1.3.1',
                     type='lambda x: float(str(x))')
        meter_cfg = yaml.dump(
            {'metric': [dict(type='gauge',
                        name='hardware.test1',
                        unit='process',
                        snmp_inspector=param),
                        dict(type='gauge',
                        name='hardware.test2.abc',
                        unit='process',
                        snmp_inspector=param)]})
        self._setup_meter_def_file(meter_cfg)
        pollster = generic.GenericHardwareDeclarativePollster
        # Clear cached mapping
        pollster.mapping = None
        exts = pollster.get_pollsters_extensions(self.conf)
        self.assertEqual(2, len(exts))
        self.assertIn(exts[0].name, ['hardware.test1', 'hardware.test2.abc'])
        self.assertIn(exts[1].name, ['hardware.test1', 'hardware.test2.abc'])
