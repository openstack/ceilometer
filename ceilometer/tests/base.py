# Copyright 2012 New Dream Network (DreamHost)
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
"""Test base classes.
"""
import functools
import os
import tempfile
import unittest
from unittest import mock

import fixtures
from oslo_config import cfg
from oslo_log import log
import oslo_messaging.conffixture
from oslotest import base
import yaml

import ceilometer
from ceilometer import messaging
from ceilometer.tests import fixtures as ceilo_fixtures
from ceilometer.tests.unit import fakes

CONF = cfg.CONF
try:
    log.register_options(CONF)
except cfg.ArgsAlreadyParsedError:
    pass
CONF.set_override('use_stderr', False)


class BaseTestCase(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        if os.environ.get('OS_LOG_CAPTURE') in ('True', 'true', '1', 'yes'):
            self.stdlog = self.useFixture(ceilo_fixtures.StandardLogging())
        self.addCleanup(CONF.reset)
        _fix = self.useFixture(ceilo_fixtures.FakeConnectionFixture())
        self.fake_conn = _fix.fake_conn
        self.fake_conn_class_mock = _fix.connection_class_mock

    def setup_connection(self, **kwargs):
        """Convenience method to allow re-defining the fake connection members

        Used if the default Connection is not sufficient for testing
        e.g. if you need some resources empty, or want duplicates to force a
        particular behaviour in the test.
        """
        self.fake_conn = mock.Mock(wraps=fakes.FakeConnection(**kwargs))
        # This should be called before any code-under-test is run, but just in
        # case someone calls setup_connection mid-test, resetting the mock
        # prevents confusing AssertionErrors when checking the call count.
        self.fake_conn_class_mock.reset_mock()
        self.fake_conn_class_mock.return_value = self.fake_conn

    def setup_messaging(self, conf, exchange=None):
        self.useFixture(oslo_messaging.conffixture.ConfFixture(conf))
        conf.set_override("notification_driver", ["messaging"])
        if not exchange:
            exchange = 'ceilometer'
        conf.set_override("control_exchange", exchange)

        # NOTE(sileht): Ensure a new oslo.messaging driver is loaded
        # between each tests
        self.transport = messaging.get_transport(conf, "fake://", cache=False)
        self.useFixture(fixtures.MockPatch(
            'ceilometer.messaging.get_transport',
            return_value=self.transport))

    def cfg2file(self, data):
        cfgfile = tempfile.NamedTemporaryFile(mode='w', delete=False)
        self.addCleanup(os.remove, cfgfile.name)
        cfgfile.write(yaml.safe_dump(data))
        cfgfile.close()
        return cfgfile.name

    @staticmethod
    def path_get(project_file=None):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                            '..',
                                            '..',
                                            )
                               )
        if project_file:
            return os.path.join(root, project_file)
        else:
            return root


def _skip_decorator(func):
    @functools.wraps(func)
    def skip_if_not_implemented(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ceilometer.NotImplementedError as e:
            raise unittest.SkipTest(str(e))
    return skip_if_not_implemented


class SkipNotImplementedMeta(type):
    def __new__(cls, name, bases, local):
        for attr in local:
            value = local[attr]
            if callable(value) and (
                    attr.startswith('test_') or attr == 'setUp'):
                local[attr] = _skip_decorator(value)
        return type.__new__(cls, name, bases, local)
