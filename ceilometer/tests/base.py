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

import fixtures
import oslo_messaging.conffixture
from oslo_utils import timeutils
from oslotest import base
import six
from testtools import testcase
import webtest
import yaml

import ceilometer
from ceilometer import messaging


class BaseTestCase(base.BaseTestCase):
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

    def assertTimestampEqual(self, first, second, msg=None):
        """Checks that two timestamps are equals.

        This relies on assertAlmostEqual to avoid rounding problem, and only
        checks up the first microsecond values.

        """
        return self.assertAlmostEqual(
            timeutils.delta_seconds(first, second),
            0.0,
            places=5)

    def assertIsEmpty(self, obj):
        try:
            if len(obj) != 0:
                self.fail("%s is not empty" % type(obj))
        except (TypeError, AttributeError):
            self.fail("%s doesn't have length" % type(obj))

    def assertIsNotEmpty(self, obj):
        try:
            if len(obj) == 0:
                self.fail("%s is empty" % type(obj))
        except (TypeError, AttributeError):
            self.fail("%s doesn't have length" % type(obj))

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
            raise testcase.TestSkipped(six.text_type(e))
        except webtest.app.AppError as e:
            if 'not implemented' in six.text_type(e):
                raise testcase.TestSkipped(six.text_type(e))
            raise
    return skip_if_not_implemented


class SkipNotImplementedMeta(type):
    def __new__(cls, name, bases, local):
        for attr in local:
            value = local[attr]
            if callable(value) and (
                    attr.startswith('test_') or attr == 'setUp'):
                local[attr] = _skip_decorator(value)
        return type.__new__(cls, name, bases, local)
