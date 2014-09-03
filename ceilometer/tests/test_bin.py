#!/usr/bin/env python
#
# Copyright 2012 eNovance <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
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

import json
import os
import random
import socket
import subprocess
import time

import httplib2

from ceilometer.openstack.common import fileutils
from ceilometer.tests import base


class BinTestCase(base.BaseTestCase):
    def setUp(self):
        super(BinTestCase, self).setUp()
        content = ("[DEFAULT]\n"
                   "rpc_backend=fake\n"
                   "[database]\n"
                   "connection=log://localhost\n")
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')

    def tearDown(self):
        super(BinTestCase, self).tearDown()
        os.remove(self.tempfile)

    def test_dbsync_run(self):
        subp = subprocess.Popen(['ceilometer-dbsync',
                                 "--config-file=%s" % self.tempfile])
        self.assertEqual(0, subp.wait())

    def test_run_expirer_ttl_disabled(self):
        subp = subprocess.Popen(['ceilometer-expirer',
                                 '-d',
                                 "--config-file=%s" % self.tempfile],
                                stderr=subprocess.PIPE)
        __, err = subp.communicate()
        self.assertEqual(0, subp.poll())
        self.assertIn("Nothing to clean", err)

    def test_run_expirer_ttl_enabled(self):
        content = ("[DEFAULT]\n"
                   "rpc_backend=fake\n"
                   "[database]\n"
                   "time_to_live=1\n"
                   "connection=log://localhost\n")
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')
        subp = subprocess.Popen(['ceilometer-expirer',
                                 '-d',
                                 "--config-file=%s" % self.tempfile],
                                stderr=subprocess.PIPE)
        __, err = subp.communicate()
        self.assertEqual(0, subp.poll())
        self.assertIn("Dropping data with TTL 1", err)


class BinSendSampleTestCase(base.BaseTestCase):
    def setUp(self):
        super(BinSendSampleTestCase, self).setUp()
        pipeline_cfg_file = self.path_get('etc/ceilometer/pipeline.yaml')
        content = ("[DEFAULT]\n"
                   "rpc_backend=fake\n"
                   "pipeline_cfg_file={0}\n".format(pipeline_cfg_file))

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


class BinAlarmEvaluatorServiceTestCase(base.BaseTestCase):
    def _do_test(self, driver, driver_class):
        pipeline_cfg_file = self.path_get('etc/ceilometer/pipeline.yaml')
        content = ("[DEFAULT]\n"
                   "rpc_backend=fake\n"
                   "pipeline_cfg_file={0}\n"
                   "debug=true\n"
                   "[database]\n"
                   "time_to_live=1\n"
                   "connection=log://localhost\n".format(pipeline_cfg_file))

        if driver:
            content += "[alarm]\nevaluation_service=%s\n" % driver

        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')
        self.subp = subprocess.Popen(['ceilometer-alarm-evaluator',
                                      "--config-file=%s" % self.tempfile],
                                     stderr=subprocess.PIPE)
        err = self.subp.stderr.read(1024)
        self.assertIn("Alarm evaluator loaded: %s" % driver_class, err)

    def tearDown(self):
        super(BinAlarmEvaluatorServiceTestCase, self).tearDown()
        self.subp.kill()
        self.subp.wait()
        os.remove(self.tempfile)

    def test_default_config(self):
        self._do_test(None, "AlarmEvaluationService")

    def test_singleton_driver(self):
        self._do_test('singleton', "SingletonAlarmService")

    def test_backward_compat(self):
        self._do_test("ceilometer.alarm.service.PartitionedAlarmService",
                      "PartitionedAlarmService")

    def test_partitioned_driver(self):
        self._do_test("partitioned", "PartitionedAlarmService")


class BinApiTestCase(base.BaseTestCase):

    def setUp(self):
        super(BinApiTestCase, self).setUp()
        # create api_paste.ini file without authentication
        content = ("[pipeline:main]\n"
                   "pipeline = api-server\n"
                   "[app:api-server]\n"
                   "paste.app_factory = ceilometer.api.app:app_factory\n")
        self.paste = fileutils.write_to_tempfile(content=content,
                                                 prefix='api_paste',
                                                 suffix='.ini')

        # create ceilometer.conf file
        self.api_port = random.randint(10000, 11000)
        self.http = httplib2.Http()
        pipeline_cfg_file = self.path_get('etc/ceilometer/pipeline.yaml')
        policy_file = self.path_get('etc/ceilometer/policy.json')
        content = ("[DEFAULT]\n"
                   "rpc_backend=fake\n"
                   "auth_strategy=noauth\n"
                   "debug=true\n"
                   "pipeline_cfg_file={0}\n"
                   "policy_file={1}\n"
                   "api_paste_config={2}\n"
                   "[api]\n"
                   "port={3}\n"
                   "[database]\n"
                   "connection=log://localhost\n".format(pipeline_cfg_file,
                                                         policy_file,
                                                         self.paste,
                                                         self.api_port))

        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='ceilometer',
                                                    suffix='.conf')
        self.subp = subprocess.Popen(['ceilometer-api',
                                      "--config-file=%s" % self.tempfile])

    def tearDown(self):
        super(BinApiTestCase, self).tearDown()
        self.subp.kill()
        self.subp.wait()
        os.remove(self.tempfile)

    def get_response(self, path):
        url = 'http://%s:%d/%s' % ('127.0.0.1', self.api_port, path)

        for x in range(10):
            try:
                r, c = self.http.request(url, 'GET')
            except socket.error:
                time.sleep(.5)
                self.assertIsNone(self.subp.poll())
            else:
                return r, c
        return None, None

    def test_v2(self):
        response, content = self.get_response('v2/meters')
        self.assertEqual(200, response.status)
        self.assertEqual([], json.loads(content))
