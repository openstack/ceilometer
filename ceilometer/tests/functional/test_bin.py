# Copyright 2012 eNovance <licensing@enovance.com>
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

import os
import subprocess
import time

from oslo_utils import fileutils
import six

from ceilometer.tests import base


class BinTestCase(base.BaseTestCase):
    def setUp(self):
        super(BinTestCase, self).setUp()
        content = ("[DEFAULT]\n"
                   "transport_url = fake://\n"
                   "[database]\n"
                   "connection=log://localhost\n")
        if six.PY3:
            content = content.encode('utf-8')
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')

    def tearDown(self):
        super(BinTestCase, self).tearDown()
        os.remove(self.tempfile)

    def test_upgrade_run(self):
        subp = subprocess.Popen(['ceilometer-upgrade',
                                 '--skip-gnocchi-resource-types',
                                 "--config-file=%s" % self.tempfile])
        self.assertEqual(0, subp.wait())

    def test_run_expirer_ttl_disabled(self):
        subp = subprocess.Popen(['ceilometer-expirer',
                                 '-d',
                                 "--config-file=%s" % self.tempfile],
                                stdout=subprocess.PIPE)
        stdout, __ = subp.communicate()
        self.assertEqual(0, subp.poll())
        self.assertIn(b"Nothing to clean, database metering "
                      b"time to live is disabled", stdout)

    def _test_run_expirer_ttl_enabled(self, ttl_name, data_name):
        content = ("[DEFAULT]\n"
                   "transport_url = fake://\n"
                   "[database]\n"
                   "%s=1\n"
                   "connection=log://localhost\n" % ttl_name)
        if six.PY3:
            content = content.encode('utf-8')
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')
        subp = subprocess.Popen(['ceilometer-expirer',
                                 '-d',
                                 "--config-file=%s" % self.tempfile],
                                stdout=subprocess.PIPE)
        stdout, __ = subp.communicate()
        self.assertEqual(0, subp.poll())
        msg = "Dropping %s data with TTL 1" % data_name
        if six.PY3:
            msg = msg.encode('utf-8')
        self.assertIn(msg, stdout)

    def test_run_expirer_ttl_enabled(self):
        self._test_run_expirer_ttl_enabled('metering_time_to_live',
                                           'metering')
        self._test_run_expirer_ttl_enabled('time_to_live', 'metering')


class BinSendSampleTestCase(base.BaseTestCase):
    def setUp(self):
        super(BinSendSampleTestCase, self).setUp()
        pipeline_cfg_file = self.path_get(
            'ceilometer/pipeline/data/pipeline.yaml')
        content = ("[DEFAULT]\n"
                   "transport_url = fake://\n"
                   "pipeline_cfg_file={0}\n".format(pipeline_cfg_file))
        if six.PY3:
            content = content.encode('utf-8')

        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')

    def tearDown(self):
        super(BinSendSampleTestCase, self).tearDown()
        os.remove(self.tempfile)

    def test_send_counter_run(self):
        subp = subprocess.Popen(['ceilometer-send-sample',
                                 "--config-file=%s" % self.tempfile,
                                 "--sample-resource=someuuid",
                                 "--sample-name=mycounter"])
        self.assertEqual(0, subp.wait())


class BinCeilometerPollingServiceTestCase(base.BaseTestCase):
    def setUp(self):
        super(BinCeilometerPollingServiceTestCase, self).setUp()
        self.tempfile = None
        self.subp = None

    def tearDown(self):
        if self.subp:
            try:
                self.subp.kill()
            except OSError:
                pass
        os.remove(self.tempfile)
        super(BinCeilometerPollingServiceTestCase, self).tearDown()

    def test_starting_with_duplication_namespaces(self):
        content = ("[DEFAULT]\n"
                   "transport_url = fake://\n"
                   "[database]\n"
                   "connection=log://localhost\n")
        if six.PY3:
            content = content.encode('utf-8')
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')
        self.subp = subprocess.Popen(['ceilometer-polling',
                                      "--config-file=%s" % self.tempfile,
                                      "--polling-namespaces",
                                      "compute",
                                      "compute"],
                                     stderr=subprocess.PIPE)
        expected = (b'Duplicated values: [\'compute\', \'compute\'] '
                    b'found in CLI options, auto de-duplicated')
        # NOTE(gordc): polling process won't quit so wait for a bit and check
        start = time.time()
        while time.time() - start < 5:
            output = self.subp.stderr.readline()
            if expected in output:
                break
        else:
            self.fail('Did not detect expected warning: %s' % expected)

    def test_polling_namespaces_invalid_value_in_config(self):
        content = ("[DEFAULT]\n"
                   "transport_url = fake://\n"
                   "polling_namespaces = ['central']\n"
                   "[database]\n"
                   "connection=log://localhost\n")
        if six.PY3:
            content = content.encode('utf-8')
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')
        self.subp = subprocess.Popen(
            ["ceilometer-polling", "--config-file=%s" % self.tempfile],
            stderr=subprocess.PIPE)
        __, err = self.subp.communicate()
        expected = ("Exception: Valid values are ['compute', 'central', "
                    "'ipmi'], but found [\"['central']\"]")
        self.assertIn(expected, err)
