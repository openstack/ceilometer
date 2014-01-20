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

import six

import mock
import webob

from ceilometer.objectstore import swift_middleware
from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common.fixture.mockpatch import PatchObject
from ceilometer.openstack.common import test
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


class TestSwiftMiddleware(test.BaseTestCase):

    class _faux_pipeline_manager(pipeline.PipelineManager):
        class _faux_pipeline(object):
            def __init__(self, pipeline_manager):
                self.pipeline_manager = pipeline_manager
                self.samples = []

            def publish_samples(self, ctxt, samples):
                self.samples.extend(samples)

            def flush(self, context):
                pass

        def __init__(self):
            self.pipelines = [self._faux_pipeline(self)]

    def _fake_setup_pipeline(self, transformer_manager):
        return self.pipeline_manager

    def setUp(self):
        super(TestSwiftMiddleware, self).setUp()
        self.pipeline_manager = self._faux_pipeline_manager()
        self.useFixture(PatchObject(pipeline, 'setup_pipeline',
                                    side_effect=self._fake_setup_pipeline))
        self.CONF = self.useFixture(config.Config()).conf

    @staticmethod
    def start_response(*args):
            pass

    def test_rpc_setup(self):
        swift_middleware.CeilometerMiddleware(FakeApp(), {})
        self.assertEqual(self.CONF.control_exchange, 'ceilometer')

    def test_get(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = webob.Request.blank('/1.0/account/container/obj',
                                  environ={'REQUEST_METHOD': 'GET'})
        resp = app(req.environ, self.start_response)
        self.assertEqual(list(resp), ["This string is 28 bytes long"])
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(len(samples), 2)
        data = samples[0]
        self.assertEqual(data.volume, 28)
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertEqual(data.resource_metadata['object'], 'obj')

        # test the # of request and the request method
        data = samples[1]
        self.assertEqual(data.name, 'storage.api.request')
        self.assertEqual(data.volume, 1)
        self.assertEqual(data.resource_metadata['method'], 'get')

    def test_put(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(body=['']), {})
        req = webob.Request.blank('/1.0/account/container/obj',
                                  environ={'REQUEST_METHOD': 'PUT',
                                           'wsgi.input':
                                           six.moves.cStringIO('some stuff')})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(len(samples), 2)
        data = samples[0]
        self.assertEqual(data.volume, 10)
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertEqual(data.resource_metadata['object'], 'obj')

        # test the # of request and the request method
        data = samples[1]
        self.assertEqual(data.name, 'storage.api.request')
        self.assertEqual(data.volume, 1)
        self.assertEqual(data.resource_metadata['method'], 'put')

    def test_post(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(body=['']), {})
        req = webob.Request.blank(
            '/1.0/account/container/obj',
            environ={'REQUEST_METHOD': 'POST',
                     'wsgi.input': six.moves.cStringIO('some other stuff')})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(len(samples), 2)
        data = samples[0]
        self.assertEqual(data.volume, 16)
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertEqual(data.resource_metadata['object'], 'obj')

        # test the # of request and the request method
        data = samples[1]
        self.assertEqual(data.name, 'storage.api.request')
        self.assertEqual(data.volume, 1)
        self.assertEqual(data.resource_metadata['method'], 'post')

    def test_head(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(body=['']), {})
        req = webob.Request.blank('/1.0/account/container/obj',
                                  environ={'REQUEST_METHOD': 'HEAD'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(len(samples), 1)
        data = samples[0]
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertEqual(data.resource_metadata['object'], 'obj')
        self.assertEqual(data.resource_metadata['method'], 'head')

        self.assertEqual(data.name, 'storage.api.request')
        self.assertEqual(data.volume, 1)

    def test_bogus_request(self):
        """Test even for arbitrary request method, this will still work."""
        app = swift_middleware.CeilometerMiddleware(FakeApp(body=['']), {})
        req = webob.Request.blank('/1.0/account/container/obj',
                                  environ={'REQUEST_METHOD': 'BOGUS'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples

        self.assertEqual(len(samples), 1)
        data = samples[0]
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertEqual(data.resource_metadata['object'], 'obj')
        self.assertEqual(data.resource_metadata['method'], 'bogus')

        self.assertEqual(data.name, 'storage.api.request')
        self.assertEqual(data.volume, 1)

    def test_get_container(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = webob.Request.blank('/1.0/account/container',
                                  environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(len(samples), 2)
        data = samples[0]
        self.assertEqual(data.volume, 28)
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertIsNone(data.resource_metadata['object'])

    def test_no_metadata_headers(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = webob.Request.blank('/1.0/account/container',
                                  environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(len(samples), 2)
        data = samples[0]
        http_headers = [k for k in data.resource_metadata.keys()
                        if k.startswith('http_header_')]
        self.assertEqual(len(http_headers), 0)
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertIsNone(data.resource_metadata['object'])

    def test_metadata_headers(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {
            'metadata_headers': 'X_VAR1, x-var2, x-var3'
        })
        req = webob.Request.blank('/1.0/account/container',
                                  environ={'REQUEST_METHOD': 'GET'},
                                  headers={'X_VAR1': 'value1',
                                           'X_VAR2': 'value2'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(len(samples), 2)
        data = samples[0]
        http_headers = [k for k in data.resource_metadata.keys()
                        if k.startswith('http_header_')]
        self.assertEqual(len(http_headers), 2)
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertIsNone(data.resource_metadata['object'])
        self.assertEqual(data.resource_metadata['http_header_x_var1'],
                         'value1')
        self.assertEqual(data.resource_metadata['http_header_x_var2'],
                         'value2')
        self.assertFalse('http_header_x_var3' in data.resource_metadata)

    def test_metadata_headers_on_not_existing_header(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {
            'metadata_headers': 'x-var3'
        })
        req = webob.Request.blank('/1.0/account/container',
                                  environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(len(samples), 2)
        data = samples[0]
        http_headers = [k for k in data.resource_metadata.keys()
                        if k.startswith('http_header_')]
        self.assertEqual(len(http_headers), 0)
        self.assertEqual(data.resource_metadata['version'], '1.0')
        self.assertEqual(data.resource_metadata['container'], 'container')
        self.assertIsNone(data.resource_metadata['object'])

    def test_bogus_path(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = webob.Request.blank('//v1/account/container',
                                  environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(len(samples), 0)

    def test_missing_resource_id(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = webob.Request.blank('/5.0/', environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(len(samples), 0)

    @mock.patch.object(swift_middleware.CeilometerMiddleware,
                       'publish_sample')
    def test_publish_sample_fail(self, mocked_publish_sample):
        mocked_publish_sample.side_effect = Exception("a exception")
        app = swift_middleware.CeilometerMiddleware(FakeApp(body=["test"]), {})
        req = webob.Request.blank('/1.0/account/container',
                                  environ={'REQUEST_METHOD': 'GET'})
        resp = list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(len(samples), 0)
        self.assertEqual(resp, ["test"])
        mocked_publish_sample.assert_called_once_with(mock.ANY, 0, 4)

    def test_reseller_prefix(self):
        # No reseller prefix set: ensure middleware uses AUTH_
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = webob.Request.blank('/1.0/AUTH_account/container/obj',
                                  environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples[0]
        self.assertEqual(samples.resource_id, "account")

        # Custom reseller prefix set
        app = swift_middleware.CeilometerMiddleware(
            FakeApp(), {'reseller_prefix': 'CUSTOM_'})
        req = webob.Request.blank('/1.0/CUSTOM_account/container/obj',
                                  environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples[0]
        self.assertEqual(samples.resource_id, "account")

    def test_invalid_reseller_prefix(self):
        # Custom reseller prefix set, but without trailing underscore
        app = swift_middleware.CeilometerMiddleware(
            FakeApp(), {'reseller_prefix': 'CUSTOM'})
        req = webob.Request.blank('/1.0/CUSTOM_account/container/obj',
                                  environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples[0]
        self.assertEqual(samples.resource_id, "account")
