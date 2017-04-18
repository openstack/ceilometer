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

from debtcollector import removals
from oslo_config import cfg
from oslo_log import log
from oslo_utils import strutils
import requests

from ceilometer import dispatcher

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
    cfg.StrOpt('verify_ssl',
               help='The path to a server certificate or directory if the '
                    'system CAs are not used or if a self-signed certificate '
                    'is used. Set to False to ignore SSL cert verification.'),
    cfg.BoolOpt('batch_mode',
                default=False,
                help='Indicates whether samples are published in a batch.'),
]


@removals.removed_class("HttpDispatcher", message="Use http publisher instead",
                        removal_version="9.0.0")
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
        # No SSL verification
        #verify_ssl = False
        # SSL verification with system-installed CAs
        verify_ssl = True
        # SSL verification with specific CA or directory of certs
        #verify_ssl = /path/to/ca_certificate.crt

    Instead of publishing events and meters as JSON objects in individual HTTP
    requests, they can be batched up and published as JSON arrays of objects::

        [dispatcher_http]
        batch_mode = True
    """

    def __init__(self, conf):
        super(HttpDispatcher, self).__init__(conf)
        self.headers = {'Content-type': 'application/json'}
        self.timeout = self.conf.dispatcher_http.timeout
        self.target = self.conf.dispatcher_http.target
        self.event_target = (self.conf.dispatcher_http.event_target or
                             self.target)

        if self.conf.dispatcher_http.batch_mode:
            self.post_event_data = self.post_event
            self.post_meter_data = self.post_meter
        else:
            self.post_event_data = self.post_individual_events
            self.post_meter_data = self.post_individual_meters

        try:
            self.verify_ssl = strutils.bool_from_string(
                self.conf.dispatcher_http.verify_ssl, strict=True)
        except ValueError:
            self.verify_ssl = self.conf.dispatcher_http.verify_ssl or True

    def record_metering_data(self, data):
        if self.target == '':
            # if the target was not set, do not do anything
            LOG.error('Dispatcher target was not set, no meter will '
                      'be posted. Set the target in the ceilometer.conf '
                      'file.')
            return

        # We may have receive only one counter on the wire
        if not isinstance(data, list):
            data = [data]

        self.post_meter_data(data)

    def post_individual_meters(self, meters):
        for meter in meters:
            self.post_meter(meter)

    def post_meter(self, meter):
        meter_json = json.dumps(meter)
        res = None
        try:
            LOG.trace('Meter Message: %s', meter_json)
            res = requests.post(self.target,
                                data=meter_json,
                                headers=self.headers,
                                verify=self.verify_ssl,
                                timeout=self.timeout)
            LOG.debug('Meter message posting finished with status code '
                      '%d.', res.status_code)
            res.raise_for_status()

        except requests.exceptions.HTTPError:
            LOG.exception('Status Code: %(code)s. '
                          'Failed to dispatch meter: %(meter)s' %
                          {'code': res.status_code, 'meter': meter_json})

    def record_events(self, events):
        if self.event_target == '':
            # if the event target was not set, do not do anything
            LOG.error('Dispatcher event target was not set, no event will '
                      'be posted. Set event_target in the ceilometer.conf '
                      'file.')
            return

        if not isinstance(events, list):
            events = [events]

        self.post_event_data(events)

    def post_individual_events(self, events):
        for event in events:
            self.post_event(event)

    def post_event(self, event):
        res = None
        try:
            event_json = json.dumps(event)
            LOG.trace('Event Message: %s', event_json)
            res = requests.post(self.event_target,
                                data=event_json,
                                headers=self.headers,
                                verify=self.verify_ssl,
                                timeout=self.timeout)
            LOG.debug('Event Message posting to %s: status code %d.',
                      self.event_target, res.status_code)
            res.raise_for_status()
        except requests.exceptions.HTTPError:
            LOG.exception('Status Code: %(code)s. '
                          'Failed to dispatch event: %(event)s' %
                          {'code': res.status_code, 'event': event_json})
