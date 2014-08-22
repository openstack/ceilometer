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

import mock
from oslo.config import fixture as fixture_config
from oslotest import mockpatch
import six

from ceilometer.objectstore import swift_middleware
from ceilometer import pipeline
from ceilometer.tests import base as tests_base


class FakeApp(object):
    def __init__(self, body=None):

        self.body = body or ['This string is 28 bytes long']

    def __call__(self, env, start_response):
        yield
        start_response('200 OK', [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(sum(map(len, self.body))))
        ])
        while env['wsgi.input'].read(5):
            pass
        for line in self.body:
            yield line


class FakeRequest(object):
    """A bare bones request object

    The middleware will inspect this for request method,
    wsgi.input and headers.
    """

    def __init__(self, path, environ=None, headers=None):
        environ = environ or {}
        headers = headers or {}

        environ['PATH_INFO'] = path

        if 'wsgi.input' not in environ:
            environ['wsgi.input'] = six.moves.cStringIO('')

        for header, value in headers.iteritems():
            environ['HTTP_%s' % header.upper()] = value
        self.environ = environ


class TestSwiftMiddleware(tests_base.BaseTestCase):

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

    def _fake_setup_pipeline(self, transformer_manager=None):
        return self.pipeline_manager

    def setUp(self):
        super(TestSwiftMiddleware, self).setUp()
        self.pipeline_manager = self._faux_pipeline_manager()
        self.useFixture(mockpatch.PatchObject(
            pipeline, 'setup_pipeline',
            side_effect=self._fake_setup_pipeline))
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.setup_messaging(self.CONF)

    @staticmethod
    def start_response(*args):
            pass

    def test_get(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = FakeRequest('/1.0/account/container/obj',
                          environ={'REQUEST_METHOD': 'GET'})
        resp = app(req.environ, self.start_response)
        self.assertEqual(["This string is 28 bytes long"], list(resp))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(2, len(samples))
        data = samples[0]
        self.assertEqual(28, data.volume)
        self.assertEqual('1.0', data.resource_metadata['version'])
        self.assertEqual('container', data.resource_metadata['container'])
        self.assertEqual('obj', data.resource_metadata['object'])

        # test the # of request and the request method
        data = samples[1]
        self.assertEqual('storage.api.request', data.name)
        self.assertEqual(1, data.volume)
        self.assertEqual('get', data.resource_metadata['method'])

    def test_put(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(body=['']), {})
        req = FakeRequest(
            '/1.0/account/container/obj',
            environ={'REQUEST_METHOD': 'PUT',
                     'wsgi.input':
                     six.moves.cStringIO('some stuff')})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(2, len(samples))
        data = samples[0]
        self.assertEqual(10, data.volume)
        self.assertEqual('1.0', data.resource_metadata['version'])
        self.assertEqual('container', data.resource_metadata['container'])
        self.assertEqual('obj', data.resource_metadata['object'])

        # test the # of request and the request method
        data = samples[1]
        self.assertEqual('storage.api.request', data.name)
        self.assertEqual(1, data.volume)
        self.assertEqual('put', data.resource_metadata['method'])

    def test_post(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(body=['']), {})
        req = FakeRequest(
            '/1.0/account/container/obj',
            environ={'REQUEST_METHOD': 'POST',
                     'wsgi.input': six.moves.cStringIO('some other stuff')})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(2, len(samples))
        data = samples[0]
        self.assertEqual(16, data.volume)
        self.assertEqual('1.0', data.resource_metadata['version'])
        self.assertEqual('container', data.resource_metadata['container'])
        self.assertEqual('obj', data.resource_metadata['object'])

        # test the # of request and the request method
        data = samples[1]
        self.assertEqual('storage.api.request', data.name)
        self.assertEqual(1, data.volume)
        self.assertEqual('post', data.resource_metadata['method'])

    def test_head(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(body=['']), {})
        req = FakeRequest('/1.0/account/container/obj',
                          environ={'REQUEST_METHOD': 'HEAD'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(1, len(samples))
        data = samples[0]
        self.assertEqual('1.0', data.resource_metadata['version'])
        self.assertEqual('container', data.resource_metadata['container'])
        self.assertEqual('obj', data.resource_metadata['object'])
        self.assertEqual('head', data.resource_metadata['method'])

        self.assertEqual('storage.api.request', data.name)
        self.assertEqual(1, data.volume)

    def test_bogus_request(self):
        """Test even for arbitrary request method, this will still work."""
        app = swift_middleware.CeilometerMiddleware(FakeApp(body=['']), {})
        req = FakeRequest('/1.0/account/container/obj',
                          environ={'REQUEST_METHOD': 'BOGUS'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples

        self.assertEqual(1, len(samples))
        data = samples[0]
        self.assertEqual('1.0', data.resource_metadata['version'])
        self.assertEqual('container', data.resource_metadata['container'])
        self.assertEqual('obj', data.resource_metadata['object'])
        self.assertEqual('bogus', data.resource_metadata['method'])

        self.assertEqual('storage.api.request', data.name)
        self.assertEqual(1, data.volume)

    def test_get_container(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = FakeRequest('/1.0/account/container',
                          environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(2, len(samples))
        data = samples[0]
        self.assertEqual(28, data.volume)
        self.assertEqual('1.0', data.resource_metadata['version'])
        self.assertEqual('container', data.resource_metadata['container'])
        self.assertIsNone(data.resource_metadata['object'])

    def test_no_metadata_headers(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = FakeRequest('/1.0/account/container',
                          environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(2, len(samples))
        data = samples[0]
        http_headers = [k for k in data.resource_metadata.keys()
                        if k.startswith('http_header_')]
        self.assertEqual(0, len(http_headers))
        self.assertEqual('1.0', data.resource_metadata['version'])
        self.assertEqual('container', data.resource_metadata['container'])
        self.assertIsNone(data.resource_metadata['object'])

    def test_metadata_headers(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {
            'metadata_headers': 'X_VAR1, x-var2, x-var3'
        })
        req = FakeRequest('/1.0/account/container',
                          environ={'REQUEST_METHOD': 'GET'},
                          headers={'X_VAR1': 'value1',
                                   'X_VAR2': 'value2'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(2, len(samples))
        data = samples[0]
        http_headers = [k for k in data.resource_metadata.keys()
                        if k.startswith('http_header_')]
        self.assertEqual(2, len(http_headers))
        self.assertEqual('1.0', data.resource_metadata['version'])
        self.assertEqual('container', data.resource_metadata['container'])
        self.assertIsNone(data.resource_metadata['object'])
        self.assertEqual('value1',
                         data.resource_metadata['http_header_x_var1'])
        self.assertEqual('value2',
                         data.resource_metadata['http_header_x_var2'])
        self.assertFalse('http_header_x_var3' in data.resource_metadata)

    def test_metadata_headers_on_not_existing_header(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {
            'metadata_headers': 'x-var3'
        })
        req = FakeRequest('/1.0/account/container',
                          environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(2, len(samples))
        data = samples[0]
        http_headers = [k for k in data.resource_metadata.keys()
                        if k.startswith('http_header_')]
        self.assertEqual(0, len(http_headers))
        self.assertEqual('1.0', data.resource_metadata['version'])
        self.assertEqual('container', data.resource_metadata['container'])
        self.assertIsNone(data.resource_metadata['object'])

    def test_bogus_path(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = FakeRequest('/5.0//',
                          environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(0, len(samples))

    def test_missing_resource_id(self):
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = FakeRequest('/v1/', environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(0, len(samples))

    @mock.patch.object(swift_middleware.CeilometerMiddleware,
                       'publish_sample')
    def test_publish_sample_fail(self, mocked_publish_sample):
        mocked_publish_sample.side_effect = Exception("a exception")
        app = swift_middleware.CeilometerMiddleware(FakeApp(body=["test"]), {})
        req = FakeRequest('/1.0/account/container',
                          environ={'REQUEST_METHOD': 'GET'})
        resp = list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples
        self.assertEqual(0, len(samples))
        self.assertEqual(["test"], resp)
        mocked_publish_sample.assert_called_once_with(mock.ANY, 0, 4)

    def test_reseller_prefix(self):
        # No reseller prefix set: ensure middleware uses AUTH_
        app = swift_middleware.CeilometerMiddleware(FakeApp(), {})
        req = FakeRequest('/1.0/AUTH_account/container/obj',
                          environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples[0]
        self.assertEqual("account", samples.resource_id)

        # Custom reseller prefix set
        app = swift_middleware.CeilometerMiddleware(
            FakeApp(), {'reseller_prefix': 'CUSTOM_'})
        req = FakeRequest('/1.0/CUSTOM_account/container/obj',
                          environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples[0]
        self.assertEqual("account", samples.resource_id)

    def test_invalid_reseller_prefix(self):
        # Custom reseller prefix set, but without trailing underscore
        app = swift_middleware.CeilometerMiddleware(
            FakeApp(), {'reseller_prefix': 'CUSTOM'})
        req = FakeRequest('/1.0/CUSTOM_account/container/obj',
                          environ={'REQUEST_METHOD': 'GET'})
        list(app(req.environ, self.start_response))
        samples = self.pipeline_manager.pipelines[0].samples[0]
        self.assertEqual("account", samples.resource_id)
