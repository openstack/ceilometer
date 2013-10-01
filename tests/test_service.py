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

import yaml
import subprocess
import os
import shutil
import signal
import time
import threading
from ceilometer import service
from ceilometer.tests import base


class ServiceTestCase(base.TestCase):
    def test_prepare_service(self):
        service.prepare_service([])


#NOTE(Fengqian): I have to set up a thread to parse the ouput of
#subprocess.Popen. Because readline() may block the process in
#some conditions.
class ParseOutput(threading.Thread):
    def __init__(self, input_stream, str_flag):
        super(ParseOutput, self).__init__()
        self.input_stream = input_stream
        self.str_flag = str_flag
        self.ret_stream = None
        self.ret = False
        self.thread_stop = False

    def run(self):
        while not self.thread_stop:
            next_line = self.input_stream.readline()
            if next_line == '':
                break
            if self.str_flag in next_line:
                self.ret = True
                self.ret_stream = next_line[(next_line.find(self.str_flag) +
                                            len(self.str_flag)):]
                self.stop()

    def stop(self):
        self.thread_stop = True


class ServiceRestartTest(base.TestCase):

    def setUp(self):
        super(ServiceRestartTest, self).setUp()
        self.tempfile = self.temp_config_file_path()
        self.pipeline_cfg_file = self.temp_config_file_path(name=
                                                            'pipeline.yaml')
        shutil.copy(self.path_get('etc/ceilometer/pipeline.yaml'),
                    self.pipeline_cfg_file)
        self.pipelinecfg_read_from_file()
        policy_file = self.path_get('tests/policy.json')
        with open(self.tempfile, 'w') as tmp:
            tmp.write("[DEFAULT]\n")
            tmp.write(
                "rpc_backend=ceilometer.openstack.common.rpc.impl_fake\n")
            tmp.write(
                "auth_strategy=noauth\n")
            tmp.write(
                "debug=true\n")
            tmp.write(
                "pipeline_cfg_file=%s\n" % self.pipeline_cfg_file)
            tmp.write(
                "policy_file=%s\n" % policy_file)
            tmp.write("[database]\n")
            tmp.write("connection=log://localhost\n")

    def _modify_pipeline_file(self):
        with open(self.pipeline_cfg_file, 'w') as pipe_fd:
            pipe_fd.truncate()
            pipe_fd.write(yaml.safe_dump(self.pipeline_cfg[1]))

    def pipelinecfg_read_from_file(self):
        with open(self.pipeline_cfg_file) as fd:
            data = fd.read()
        self.pipeline_cfg = yaml.safe_load(data)

    def tearDown(self):
        super(ServiceRestartTest, self).tearDown()
        self.sub.kill()
        self.sub.wait()

    @staticmethod
    def _check_process_alive(pid):
        try:
            with open("/proc/%d/status" % pid) as fd_proc:
                for line in fd_proc.readlines():
                    if line.startswith("State:"):
                        state = line.split(":", 1)[1].strip().split(' ')[0]
                        return state not in ['Z', 'T', 'Z+']
        except IOError:
            return False

    def check_process_alive(self):
        cond = lambda: self._check_process_alive(self.sub.pid)
        return self._wait(cond, 60)

    def parse_output(self, str_flag, timeout=3):
        parse = ParseOutput(self.sub.stderr, str_flag)
        parse.start()
        parse.join(timeout)
        parse.stop()
        return parse

    @staticmethod
    def _wait(cond, timeout):
        start = time.time()
        while not cond():
            if time.time() - start > timeout:
                break
            time.sleep(.1)
        return cond()

    def _spawn_service(self, cmd, conf_file=None):
        if conf_file is None:
            conf_file = self.tempfile
        self.sub = subprocess.Popen([cmd, '--config-file=%s' % conf_file],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        #NOTE(Fengqian): Parse the output to see if the service started
        self.assertTrue(self.parse_output("Starting").ret)
        self.check_process_alive()

    def _service_restart(self, cmd):
        self._spawn_service(cmd)

        self.assertTrue(self.sub.pid)
        #NOTE(Fengqian): Modify the pipleline configure file to see
        #if the file is reloaded correctly.
        self._modify_pipeline_file()
        self.pipelinecfg_read_from_file()
        os.kill(self.sub.pid, signal.SIGHUP)

        self.assertTrue(self.check_process_alive())
        self.assertTrue(self.parse_output("Caught SIGHUP").ret)
        self.assertEqual(self.pipeline_cfg,
                         yaml.safe_load(
                         self.parse_output("Pipeline config: ").ret_stream))

    def test_compute_service_restart(self):
        self._service_restart('ceilometer-agent-compute')

    def test_central_service_restart(self):
        self._service_restart('ceilometer-agent-central')
