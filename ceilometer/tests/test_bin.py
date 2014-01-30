#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
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
        content = ("[database]\n"
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
        self.assertEqual(subp.wait(), 0)

    def test_run_expirer_ttl_disabled(self):
        subp = subprocess.Popen(['ceilometer-expirer',
                                 '-d',
                                 "--config-file=%s" % self.tempfile],
                                stderr=subprocess.PIPE)
        __, err = subp.communicate()
        self.assertEqual(subp.poll(), 0)
        self.assertIn("Nothing to clean", err)

    def test_run_expirer_ttl_enabled(self):
        content = ("[database]\n"
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
        self.assertEqual(subp.poll(), 0)
        self.assertIn("Dropping data with TTL 1", err)


class BinSendSampleTestCase(base.BaseTestCase):
    def setUp(self):
        super(BinSendSampleTestCase, self).setUp()
        pipeline_cfg_file = self.path_get('etc/ceilometer/pipeline.yaml')
        content = "[DEFAULT]\n"\
                  "rpc_backend=ceilometer.openstack.common.rpc.impl_fake\n"\
                  "pipeline_cfg_file={0}\n".format(pipeline_cfg_file)

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
        self.assertEqual(subp.wait(), 0)


class BinApiTestCase(base.BaseTestCase):

    def setUp(self):
        super(BinApiTestCase, self).setUp()
        self.api_port = random.randint(10000, 11000)
        self.http = httplib2.Http()
        pipeline_cfg_file = self.path_get('etc/ceilometer/pipeline.yaml')
        policy_file = self.path_get('etc/ceilometer/policy.json')
        content = "[DEFAULT]\n"\
                  "rpc_backend=ceilometer.openstack.common.rpc.impl_fake\n"\
                  "auth_strategy=noauth\n"\
                  "debug=true\n"\
                  "pipeline_cfg_file={0}\n"\
                  "policy_file={1}\n"\
                  "[api]\n"\
                  "port={2}\n"\
                  "[database]\n"\
                  "connection=log://localhost\n".format(pipeline_cfg_file,
                                                        policy_file,
                                                        self.api_port)

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
        return (None, None)

    def test_v1(self):
        response, content = self.get_response('v1/meters')
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(content), {'meters': []})

    def test_v2(self):
        response, content = self.get_response('v2/meters')
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(content), [])
