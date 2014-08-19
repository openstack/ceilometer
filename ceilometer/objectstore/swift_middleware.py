#!/usr/bin/env python
#
# Copyright 2012 eNovance <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
Ceilometer Middleware for Swift Proxy

Configuration:

In /etc/swift/proxy-server.conf on the main pipeline add "ceilometer" just
before "proxy-server" and add the following filter in the file:

.. code-block:: python

    [filter:ceilometer]
    use = egg:ceilometer#swift

    # Some optional configuration
    # this allow to publish additional metadata
    metadata_headers = X-TEST

    # Set reseller prefix (defaults to "AUTH_" if not set)
    reseller_prefix = AUTH_
"""

from __future__ import absolute_import

from oslo.utils import timeutils

from ceilometer.openstack.common import context
from ceilometer.openstack.common import log
from ceilometer import pipeline
from ceilometer import sample
from ceilometer import service


LOG = log.getLogger(__name__)


class InputProxy(object):
    """File-like object that counts bytes read.

    To be swapped in for wsgi.input for accounting purposes.
    Borrowed from swift.common.utils. Duplidated here to avoid
    dependency on swift package.
    """
    def __init__(self, wsgi_input):
        self.wsgi_input = wsgi_input
        self.bytes_received = 0

    def read(self, *args, **kwargs):
        """Pass read request to the underlying file-like object

        Add bytes read to total.
        """
        chunk = self.wsgi_input.read(*args, **kwargs)
        self.bytes_received += len(chunk)
        return chunk

    def readline(self, *args, **kwargs):
        """Pass readline request to the underlying file-like object

        Add bytes read to total.
        """
        line = self.wsgi_input.readline(*args, **kwargs)
        self.bytes_received += len(line)
        return line


class CeilometerMiddleware(object):
    """Ceilometer middleware used for counting requests."""

    def __init__(self, app, conf):
        self.app = app

        self.metadata_headers = [h.strip().replace('-', '_').lower()
                                 for h in conf.get(
                                     "metadata_headers",
                                     "").split(",") if h.strip()]

        service.prepare_service([])

        self.pipeline_manager = pipeline.setup_pipeline()
        self.reseller_prefix = conf.get('reseller_prefix', 'AUTH_')
        if self.reseller_prefix and self.reseller_prefix[-1] != '_':
            self.reseller_prefix += '_'

    def __call__(self, env, start_response):
        start_response_args = [None]
        input_proxy = InputProxy(env['wsgi.input'])
        env['wsgi.input'] = input_proxy

        def my_start_response(status, headers, exc_info=None):
            start_response_args[0] = (status, list(headers), exc_info)

        def iter_response(iterable):
            iterator = iter(iterable)
            try:
                chunk = next(iterator)
                while not chunk:
                    chunk = next(iterator)
            except StopIteration:
                chunk = ''

            if start_response_args[0]:
                start_response(*start_response_args[0])
            bytes_sent = 0
            try:
                while chunk:
                    bytes_sent += len(chunk)
                    yield chunk
                    chunk = next(iterator)
            finally:
                try:
                    self.publish_sample(env,
                                        input_proxy.bytes_received,
                                        bytes_sent)
                except Exception:
                    LOG.exception('Failed to publish samples')

        try:
            iterable = self.app(env, my_start_response)
        except Exception:
            self.publish_sample(env, input_proxy.bytes_received, 0)
            raise
        else:
            return iter_response(iterable)

    def publish_sample(self, env, bytes_received, bytes_sent):
        path = env['PATH_INFO']
        method = env['REQUEST_METHOD']
        headers = dict((header.strip('HTTP_'), env[header]) for header
                       in env if header.startswith('HTTP_'))

        try:
            container = obj = None
            version, account, remainder = path.replace(
                '/', '', 1).split('/', 2)
            if not version or not account:
                raise ValueError('Invalid path: %s' % path)
            if remainder:
                if '/' in remainder:
                    container, obj = remainder.split('/', 1)
                else:
                    container = remainder
        except ValueError:
            return

        now = timeutils.utcnow().isoformat()

        resource_metadata = {
            "path": path,
            "version": version,
            "container": container,
            "object": obj,
        }

        for header in self.metadata_headers:
            if header.upper() in headers:
                resource_metadata['http_header_%s' % header] = headers.get(
                    header.upper())

        with self.pipeline_manager.publisher(
                context.get_admin_context()) as publisher:
            if bytes_received:
                publisher([sample.Sample(
                    name='storage.objects.incoming.bytes',
                    type=sample.TYPE_DELTA,
                    unit='B',
                    volume=bytes_received,
                    user_id=env.get('HTTP_X_USER_ID'),
                    project_id=env.get('HTTP_X_TENANT_ID'),
                    resource_id=account.partition(self.reseller_prefix)[2],
                    timestamp=now,
                    resource_metadata=resource_metadata)])

            if bytes_sent:
                publisher([sample.Sample(
                    name='storage.objects.outgoing.bytes',
                    type=sample.TYPE_DELTA,
                    unit='B',
                    volume=bytes_sent,
                    user_id=env.get('HTTP_X_USER_ID'),
                    project_id=env.get('HTTP_X_TENANT_ID'),
                    resource_id=account.partition(self.reseller_prefix)[2],
                    timestamp=now,
                    resource_metadata=resource_metadata)])

            # publish the event for each request
            # request method will be recorded in the metadata
            resource_metadata['method'] = method.lower()
            publisher([sample.Sample(
                name='storage.api.request',
                type=sample.TYPE_DELTA,
                unit='request',
                volume=1,
                user_id=env.get('HTTP_X_USER_ID'),
                project_id=env.get('HTTP_X_TENANT_ID'),
                resource_id=account.partition(self.reseller_prefix)[2],
                timestamp=now,
                resource_metadata=resource_metadata)])


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def ceilometer_filter(app):
        return CeilometerMiddleware(app, conf)
    return ceilometer_filter
