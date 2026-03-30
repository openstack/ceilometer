# Copyright 2026 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#

"""Fixtures for Ceilometer tests."""

import logging as std_logging
import os
from unittest import mock

import fixtures

from ceilometer.tests.unit import fakes


class FakeConnectionFixture(fixtures.Fixture):
    """Patches openstack.connection.Connection to return a FakeConnection spy.

    Attributes:
        fake_conn: mock.Mock wrapping the FakeConnection instance. Use this
            to assert on calls made by the code under test, e.g.
            ``fix.fake_conn.list_projects.assert_called_once_with(...)``
        connection_class_mock: the mock of the Connection class itself (the
            patched callable). Use to assert the constructor was called with
            expected args, e.g.
            ``fix.connection_class_mock.assert_called_once_with(session=...)``

    Usage::

        fix = self.useFixture(ceilo_fixtures.FakeConnectionFixture(
            projects=[fakes.PROJECT_ADMIN_sdk]))
        fix.fake_conn.list_projects.assert_called_once_with(...)
        fix.connection_class_mock.assert_called_once_with(
            session=..., oslo_conf=..., service_types=...)
    """

    def __init__(self, **kwargs):
        super().__init__()
        self._kwargs = kwargs

    def _setUp(self):
        """Patch Connection and set up return values.

        The Connection class is mocked with autospec=True, so that the
        constructor is validated at test time. This means if the code ever
        calls Connection(badkwarg=...) or if the SDK changes
        Connection.__init__'s signature, there'll be a TypeError rather than a
        silently passing test.
        """
        self.fake_conn = mock.Mock(wraps=fakes.FakeConnection(**self._kwargs))
        patcher = mock.patch(
            'openstack.connection.Connection',
            return_value=self.fake_conn,
            autospec=True
        )
        self.connection_class_mock = patcher.start()
        self.addCleanup(patcher.stop)


class NullHandler(std_logging.Handler):
    """custom default NullHandler to attempt to format the record.

    Used in conjunction with
    log_fixture.get_logging_handle_error_fixture to detect formatting errors in
    debug level logs without saving the logs.
    """

    def handle(self, record):
        self.format(record)

    def emit(self, record):
        pass

    def createLock(self):
        self.lock = None


class StandardLogging(fixtures.Fixture):
    """Setup Logging redirection for tests.

    There are a number of things we want to handle with logging in tests:

    * Redirect the logging to somewhere that we can test or dump it later.

    * Ensure that as many DEBUG messages as possible are actually
      executed, to ensure they are actually syntactically valid

    * Ensure that we create useful output for tests that doesn't
      overwhelm the testing.

    To do this we create a logger fixture at the root level, which
    defaults to INFO and create a Null Logger at DEBUG which lets
    us execute log messages at DEBUG but not keep the output.

    To support local debugging OS_DEBUG=True can be set in the
    environment, which will print out the full debug logging.
    """

    # External libraries that are excessively verbose at DEBUG/INFO level.
    # Set to WARNING so they do not flood the test output or the FakeLogger
    # capture buffer, while still surfacing WARNING-level events on failures.
    NOISY_LOGGERS = [
        'botocore',
        'keystoneauth1',
        'openstack',
        'oslo.messaging',
        'requests',
        'stevedore',
        'urllib3',
    ]

    def setUp(self):
        super().setUp()

        # set root logger to debug
        root = std_logging.getLogger()
        root.setLevel(std_logging.DEBUG)

        # Suppress verbose external library output; WARNING+ is still
        # captured by FakeLogger and surfaced when a test fails.
        for name in self.NOISY_LOGGERS:
            std_logging.getLogger(name).setLevel(std_logging.WARNING)

        # supports collecting debug level for local runs
        if os.environ.get('OS_DEBUG') in ('True', 'true', '1', 'yes'):
            level = std_logging.DEBUG
        else:
            level = std_logging.INFO

        # Collect logs
        fs = '%(asctime)s %(levelname)s [%(name)s] %(message)s'
        self.logger = self.useFixture(
            fixtures.FakeLogger(format=fs, level=None))
        root.handlers[0].setLevel(level)

        if level > std_logging.DEBUG:
            # Just attempt to format debug level logs, but don't save them
            handler = NullHandler()
            self.useFixture(fixtures.LogHandler(handler, nuke_handlers=False))
            handler.setLevel(std_logging.DEBUG)

        # At times we end up calling back into main() functions in
        # testing. This has the possibility of calling logging.setup
        # again, which completely unwinds the logging capture we've
        # created here. Once we've setup the logging the way we want,
        # disable the ability for the test to change this.
        def fake_logging_setup(*args):
            pass

        self.useFixture(
            fixtures.MonkeyPatch('oslo_log.log.setup', fake_logging_setup))
