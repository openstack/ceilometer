#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
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

from __future__ import absolute_import

from ceilometer import publish
from ceilometer import counter
from ceilometer.openstack.common import cfg
from ceilometer.openstack.common import context
from ceilometer.openstack.common import timeutils

from swift.common.utils import split_path

try:
    # Swift >= 1.7.5
    from swift.common.swob import Request
except ImportError:
    from webob import Request

try:
    # Swift > 1.7.5
    from swift.common.utils import InputProxy
except ImportError:
    # Swift <= 1.7.5
    from swift.common.middleware.proxy_logging import InputProxy


class CeilometerMiddleware(object):
    """
    Ceilometer middleware used for counting requests.
    """

    def __init__(self, app, conf):
        self.app = app
        cfg.CONF([], project='ceilometer')

    def __call__(self, env, start_response):
        start_response_args = [None]
        input_proxy = InputProxy(env['wsgi.input'])
        env['wsgi.input'] = input_proxy

        def my_start_response(status, headers, exc_info=None):
            start_response_args[0] = (status, list(headers), exc_info)

        def iter_response(iterable):
            if start_response_args[0]:
                start_response(*start_response_args[0])
            bytes_sent = 0
            try:
                for chunk in iterable:
                    if chunk:
                        bytes_sent += len(chunk)
                    yield chunk
            finally:
                self.publish_counter(env,
                                     input_proxy.bytes_received,
                                     bytes_sent)

        try:
            iterable = self.app(env, my_start_response)
        except Exception:
            self.publish_counter(env, input_proxy.bytes_received, 0)
            raise
        else:
            return iter_response(iterable)

    @staticmethod
    def publish_counter(env, bytes_received, bytes_sent):
        req = Request(env)
        version, account, container, obj = split_path(req.path, 1, 4, True)
        now = timeutils.utcnow().isoformat()

        if bytes_received:
            publish.publish_counter(context.get_admin_context(),
                                    counter.Counter(
                                        name='storage.objects.incoming.bytes',
                                        type='delta',
                                        unit='B',
                                        volume=bytes_received,
                                        user_id=env.get('HTTP_X_USER_ID'),
                                        project_id=env.get('HTTP_X_TENANT_ID'),
                                        resource_id=account.partition(
                                            'AUTH_')[2],
                                        timestamp=now,
                                        resource_metadata={
                                            "path": req.path,
                                            "version": version,
                                            "container": container,
                                            "object": obj,
                                    }),
                                    cfg.CONF.metering_topic,
                                    cfg.CONF.metering_secret,
                                    cfg.CONF.counter_source)

        if bytes_sent:
            publish.publish_counter(context.get_admin_context(),
                                    counter.Counter(
                                        name='storage.objects.outgoing.bytes',
                                        type='delta',
                                        unit='B',
                                        volume=bytes_sent,
                                        user_id=env.get('HTTP_X_USER_ID'),
                                        project_id=env.get('HTTP_X_TENANT_ID'),
                                        resource_id=account.partition(
                                            'AUTH_')[2],
                                        timestamp=now,
                                        resource_metadata={
                                            "path": req.path,
                                            "version": version,
                                            "container": container,
                                            "object": obj,
                                    }),
                                    cfg.CONF.metering_topic,
                                    cfg.CONF.metering_secret,
                                    cfg.CONF.counter_source)


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def ceilometer_filter(app):
        return CeilometerMiddleware(app, conf)
    return ceilometer_filter
