#
# Copyright 2016 IBM
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

from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import strutils
import requests
from requests import adapters
from six.moves.urllib import parse as urlparse

from ceilometer.i18n import _LE
from ceilometer import publisher

LOG = log.getLogger(__name__)


class HttpPublisher(publisher.ConfigPublisherBase):
    """Publish metering data to a http endpoint

    This publisher pushes metering data to a specified http endpoint. The
    endpoint should be configured in ceilometer pipeline configuration file.
    If the `timeout` and/or `max_retries` are not specified, the default
    `timeout` and `max_retries` will be set to 5 and 2 respectively. Additional
    parameters are:

        - ssl can be enabled by setting `verify_ssl`
        - batching can be configured by `batch`
        - connection pool size configured using `poolsize`

    To use this publisher for samples, add the following section to the
    /etc/ceilometer/pipeline.yaml file or simply add it to an existing
    pipeline::

          - name: meter_file
            interval: 600
            counters:
                - "*"
            transformers:
            publishers:
                - http://host:80/path?timeout=1&max_retries=2&batch=False

    In the event_pipeline.yaml file, you can use the publisher in one of
    the sinks like the following:

          - name: event_sink
            transformers:
            publishers:
                - http://host:80/path?timeout=1&max_retries=2

    """

    def __init__(self, conf, parsed_url):
        super(HttpPublisher, self).__init__(conf, parsed_url)
        self.target = parsed_url.geturl()

        if not parsed_url.hostname:
            raise ValueError('The hostname of an endpoint for '
                             'HttpPublisher is required')

        # non-numeric port from the url string will cause a ValueError
        # exception when the port is read. Do a read to make sure the port
        # is valid, if not, ValueError will be thrown.
        parsed_url.port

        self.headers = {'Content-type': 'application/json'}

        # Handling other configuration options in the query string
        params = urlparse.parse_qs(parsed_url.query)
        self.timeout = self._get_param(params, 'timeout', 5, int)
        self.max_retries = self._get_param(params, 'max_retries', 2, int)
        self.poster = (
            self._do_post if strutils.bool_from_string(self._get_param(
                params, 'batch', True)) else self._individual_post)
        try:
            self.verify_ssl = strutils.bool_from_string(
                self._get_param(params, 'verify_ssl', None), strict=True)
        except ValueError:
            self.verify_ssl = (self._get_param(params, 'verify_ssl', None)
                               or True)
        self.raw_only = strutils.bool_from_string(
            self._get_param(params, 'raw_only', False))

        pool_size = self._get_param(params, 'poolsize', 10, int)
        kwargs = {'max_retries': self.max_retries,
                  'pool_connections': pool_size, 'pool_maxsize': pool_size}
        self.session = requests.Session()
        # FIXME(gordc): support https in addition to http
        self.session.mount(self.target, adapters.HTTPAdapter(**kwargs))

        LOG.debug('HttpPublisher for endpoint %s is initialized!' %
                  self.target)

    @staticmethod
    def _get_param(params, name, default_value, cast=None):
        try:
            return cast(params.get(name)[-1]) if cast else params.get(name)[-1]
        except (ValueError, TypeError):
            LOG.debug('Default value %(value)s is used for %(name)s' %
                      {'value': default_value, 'name': name})
            return default_value

    def _individual_post(self, data):
        for d in data:
            self._do_post(d)

    def _do_post(self, data):
        if not data:
            LOG.debug('Data set is empty!')
            return
        data = jsonutils.dumps(data)
        LOG.trace('Message: %s', data)
        try:
            res = self.session.post(self.target, data=data,
                                    headers=self.headers, timeout=self.timeout,
                                    verify=self.verify_ssl)
            res.raise_for_status()
            LOG.debug('Message posting to %s: status code %d.',
                      self.target, res.status_code)
        except requests.exceptions.HTTPError:
            LOG.exception(_LE('Status Code: %(code)s. '
                              'Failed to dispatch message: %(data)s') %
                          {'code': res.status_code, 'data': data})

    def publish_samples(self, samples):
        """Send a metering message for publishing

        :param samples: Samples from pipeline after transformation
        """
        self.poster([sample.as_dict() for sample in samples])

    def publish_events(self, events):
        """Send an event message for publishing

        :param events: events from pipeline after transformation
        """
        if self.raw_only:
            data = [evt.as_dict()['raw']['payload'] for evt in events
                    if evt.as_dict().get('raw', {}).get('payload')]
        else:
            data = [event.serialize() for event in events]
        self.poster(data)
