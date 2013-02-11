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

import cStringIO as StringIO
from webob import Request

from ceilometer.tests import base
from ceilometer.objectstore import swift_middleware
from ceilometer import pipeline


class FakeApp(object):
    def __init__(self, body=['This string is 28 bytes long']):
        self.body = body

    def __call__(self, env, start_response):
        start_response('200 OK', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(sum(map(len, self.body))))
        ])
        while env['wsgi.input'].read(5):
            pass
        return self.body


class TestSwiftMiddleware(base.TestCase):

    class _faux_pipeline_manager():
        def __init__(self):
            self.counters = []

        def publish_counters(self, context, counters, source):
            self.counters.extend(counters)

        def publisher(self, context, source):
            return pipeline.Publisher(self, context, source)

        def flush(self, context, source):
            pass

    def _faux_setup_pipeline(self, publisher_manager):
        return self.pipeline_manager

    def setUp(self):
        super(TestSwiftMiddleware, self).setUp()
        self.pipeline_manager = self._faux_pipeline_manager()
        self.stubs.Set(pipeline, 'setup_pipeline', self._faux_setup_pipeline)

    @staticmethod
    def start_response(*args):
            pass

    def test_get(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = Request.blank('/1.0/account/container/obj',
                            environ={'REQUEST_METHOD': 'GET'})
        resp = app(req.environ, self.start_response)
        self.assertEqual(list(resp), ["This string is 28 bytes long"])
        self.assertEqual(len(self.pipeline_manager.counters), 1)
        data = self.pipeline_manager.counters[0]
        self.assertEqual(data.volume, 28)
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertEqual(data.resource_metadata['object'], 'obj')

    def test_put(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(body=['']), {})
        req = Request.blank('/1.0/account/container/obj',
                            environ={'REQUEST_METHOD': 'GET',
                                     'wsgi.input':
                                     StringIO.StringIO('some stuff')})
        resp = list(app(req.environ, self.start_response))
        self.assertEqual(len(self.pipeline_manager.counters), 1)
        data = self.pipeline_manager.counters[0]
        self.assertEqual(data.volume, 10)
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertEqual(data.resource_metadata['object'], 'obj')

    def test_post(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(body=['']), {})
        req = Request.blank('/1.0/account/container/obj',
                            environ={'REQUEST_METHOD': 'POST',
                                     'wsgi.input':
                                     StringIO.StringIO('some other stuff')})
        resp = list(app(req.environ, self.start_response))
        self.assertEqual(len(self.pipeline_manager.counters), 1)
        data = self.pipeline_manager.counters[0]
        self.assertEqual(data.volume, 16)
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertEqual(data.resource_metadata['object'], 'obj')

    def test_get_container(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = Request.blank('/1.0/account/container',
                            environ={'REQUEST_METHOD': 'GET'})
        resp = list(app(req.environ, self.start_response))
        self.assertEqual(len(self.pipeline_manager.counters), 1)
        data = self.pipeline_manager.counters[0]
        self.assertEqual(data.volume, 28)
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertEqual(data.resource_metadata['object'], None)
