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

from ceilometer.tests import base


class BinTestCase(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        content = ("[DEFAULT]\n"
                   "transport_url = fake://\n")
        content = content.encode('utf-8')
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')

    def tearDown(self):
        super().tearDown()
        os.remove(self.tempfile)

    def test_upgrade_run(self):
        subp = subprocess.Popen(['ceilometer-upgrade',
                                 '--skip-gnocchi-resource-types',
                                 "--config-file=%s" % self.tempfile])
        self.assertEqual(0, subp.wait())


class BinSendSampleTestCase(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        pipeline_cfg_file = self.path_get(
            'ceilometer/pipeline/data/pipeline.yaml')
        content = ("[DEFAULT]\n"
                   "transport_url = fake://\n"
                   "pipeline_cfg_file={}\n".format(pipeline_cfg_file))
        content = content.encode('utf-8')

        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')

    def tearDown(self):
        super().tearDown()
        os.remove(self.tempfile)

    def test_send_counter_run(self):
        subp = subprocess.Popen(['ceilometer-send-sample',
                                 "--config-file=%s" % self.tempfile,
                                 "--sample-resource=someuuid",
                                 "--sample-name=mycounter"])
        self.assertEqual(0, subp.wait())


class BinCeilometerPollingServiceTestCase(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        self.tempfile = None
        self.subp = None

    def tearDown(self):
        if self.subp:
            try:
                self.subp.kill()
            except OSError:
                pass
        os.remove(self.tempfile)
        super().tearDown()

    def test_starting_with_duplication_namespaces(self):
        content = ("[DEFAULT]\n"
                   "transport_url = fake://\n")
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
