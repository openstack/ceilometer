# Copyright 2013 IBM Corp
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

from oslo_config import cfg
from oslo_log import log
import requests

from ceilometer import dispatcher
from ceilometer.i18n import _, _LE, _LW
from ceilometer.publisher import utils as publisher_utils

LOG = log.getLogger(__name__)

http_dispatcher_opts = [
    cfg.StrOpt('target',
               default='',
               help='The target where the http request will be sent. '
                    'If this is not set, no data will be posted. For '
                    'example: target = http://hostname:1234/path'),
    cfg.StrOpt('event_target',
               help='The target for event data where the http request '
                    'will be sent to. If this is not set, it will default '
                    'to same as Sample target.'),
    cfg.IntOpt('timeout',
               default=5,
               help='The max time in seconds to wait for a request to '
                    'timeout.'),
]

cfg.CONF.register_opts(http_dispatcher_opts, group="dispatcher_http")


class HttpDispatcher(dispatcher.MeterDispatcherBase,
                     dispatcher.EventDispatcherBase):
    """Dispatcher class for posting metering/event data into a http target.

    To enable this dispatcher, the following option needs to be present in
    ceilometer.conf file::

        [DEFAULT]
        meter_dispatchers = http
        event_dispatchers = http

    Dispatcher specific options can be added as follows::

        [dispatcher_http]
        target = www.example.com
        event_target = www.example.com
        timeout = 2
    """

    def __init__(self, conf):
        super(HttpDispatcher, self).__init__(conf)
        self.headers = {'Content-type': 'application/json'}
        self.timeout = self.conf.dispatcher_http.timeout
        self.target = self.conf.dispatcher_http.target
        self.event_target = (self.conf.dispatcher_http.event_target or
                             self.target)

    def record_metering_data(self, data):
        if self.target == '':
            # if the target was not set, do not do anything
            LOG.error(_('Dispatcher target was not set, no meter will '
                        'be posted. Set the target in the ceilometer.conf '
                        'file'))
            return

        # We may have receive only one counter on the wire
        if not isinstance(data, list):
            data = [data]

        for meter in data:
            LOG.debug(
                'metering data %(counter_name)s '
                'for %(resource_id)s @ %(timestamp)s: %(counter_volume)s',
                {'counter_name': meter['counter_name'],
                 'resource_id': meter['resource_id'],
                 'timestamp': meter.get('timestamp', 'NO TIMESTAMP'),
                 'counter_volume': meter['counter_volume']})
            if publisher_utils.verify_signature(
                    meter, self.conf.publisher.telemetry_secret):
                try:
                    # Every meter should be posted to the target
                    res = requests.post(self.target,
                                        data=json.dumps(meter),
                                        headers=self.headers,
                                        timeout=self.timeout)
                    LOG.debug('Message posting finished with status code '
                              '%d.', res.status_code)
                except Exception as err:
                    LOG.exception(_('Failed to record metering data: %s'),
                                  err)
            else:
                LOG.warning(_(
                    'message signature invalid, discarding message: %r'),
                    meter)

    def record_events(self, events):
        if not isinstance(events, list):
            events = [events]

        for event in events:
            if publisher_utils.verify_signature(
                    event, self.conf.publisher.telemetry_secret):
                res = None
                try:
                    res = requests.post(self.event_target, data=event,
                                        headers=self.headers,
                                        timeout=self.timeout)
                    res.raise_for_status()
                except Exception:
                    error_code = res.status_code if res else 'unknown'
                    LOG.exception(_LE('Status Code: %{code}s. Failed to'
                                      'dispatch event: %{event}s'),
                                  {'code': error_code, 'event': event})
            else:
                LOG.warning(_LW(
                    'event signature invalid, discarding event: %s'), event)
