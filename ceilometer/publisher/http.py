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
import requests
from requests import adapters
from six.moves.urllib import parse as urlparse

from ceilometer.i18n import _LE
from ceilometer import publisher

LOG = log.getLogger(__name__)


class HttpPublisher(publisher.PublisherBase):
    """Publisher metering data to a http endpoint

    The publisher which records metering data into a http endpoint. The
    endpoint should be configured in ceilometer pipeline configuration file.
    If the timeout and/or retry_count are not specified, the default timeout
    and retry_count will be set to 1000 and 2 respectively.

    To use this publisher for samples, add the following section to the
    /etc/ceilometer/publisher.yaml file or simply add it to an existing
    pipeline::

          - name: meter_file
            interval: 600
            counters:
                - "*"
            transformers:
            publishers:
                - http://host:80/path?timeout=1&max_retries=2

    To use this publisher for events, the raw message needs to be present in
    the event. To enable that, ceilometer.conf file will need to have a
    section like the following:

        [event]
        store_raw = info

    Then in the event_pipeline.yaml file, you can use the publisher in one of
    the sinks like the following:

          - name: event_sink
            transformers:
            publishers:
                - http://host:80/path?timeout=1&max_retries=2

    Http end point is required for this publisher to work properly.
    """

    def __init__(self, parsed_url):
        super(HttpPublisher, self).__init__(parsed_url)
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
        if parsed_url.query:
            params = urlparse.parse_qs(parsed_url.query)
            self.timeout = self._get_param(params, 'timeout', 1)
            self.max_retries = self._get_param(params, 'max_retries', 2)
        else:
            self.timeout = 1
            self.max_retries = 2

        LOG.debug('HttpPublisher for endpoint %s is initialized!' %
                  self.target)

    @staticmethod
    def _get_param(params, name, default_value):
        try:
            return int(params.get(name)[-1])
        except (ValueError, TypeError):
            LOG.debug('Default value %(value)s is used for %(name)s' %
                      {'value': default_value, 'name': name})
            return default_value

    def _do_post(self, data):
        if not data:
            LOG.debug('Data set is empty!')
            return

        session = requests.Session()
        session.mount(self.target,
                      adapters.HTTPAdapter(max_retries=self.max_retries))

        content = ','.join([jsonutils.dumps(item) for item in data])
        content = '[' + content + ']'

        LOG.debug('Data to be posted by HttpPublisher: %s' % content)

        res = session.post(self.target, data=content, headers=self.headers,
                           timeout=self.timeout)
        if res.status_code >= 300:
            LOG.error(_LE('Data post failed with status code %s') %
                      res.status_code)

    def publish_samples(self, context, samples):
        """Send a metering message for publishing

        :param context: Execution context from the service or RPC call
        :param samples: Samples from pipeline after transformation
        """
        data = [sample.as_dict() for sample in samples]
        self._do_post(data)

    def publish_events(self, context, events):
        """Send an event message for publishing

        :param context: Execution context from the service or RPC call
        :param events: events from pipeline after transformation
        """
        data = [evt.as_dict()['raw']['payload'] for evt in events
                if evt.as_dict().get('raw', {}).get('payload')]
        self._do_post(data)
