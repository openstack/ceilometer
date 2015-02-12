#
# Copyright 2015 Red Hat
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

from oslo_config import cfg
from oslo_utils import timeutils

from ceilometer.dispatcher import database
from ceilometer import publisher
from ceilometer.publisher import utils


class DirectPublisher(publisher.PublisherBase):
    """A publisher that allows saving directly from the pipeline.

    Samples are saved to the currently configured database by hitching
    a ride on the DatabaseDispatcher. This is useful where it is desirable
    to limit the number of external services that are required.
    """

    def __init__(self, parsed_url):
        super(DirectPublisher, self).__init__(parsed_url)
        dispatcher = database.DatabaseDispatcher(cfg.CONF)
        self.meter_conn = dispatcher.meter_conn
        self.event_conn = dispatcher.event_conn

    def publish_samples(self, context, samples):
        if not isinstance(samples, list):
            samples = [samples]

        # Transform the Sample objects into a list of dicts
        meters = [
            utils.meter_message_from_counter(
                sample, cfg.CONF.publisher.telemetry_secret)
            for sample in samples
        ]

        for meter in meters:
            if meter.get('timestamp'):
                ts = timeutils.parse_isotime(meter['timestamp'])
                meter['timestamp'] = timeutils.normalize_time(ts)
            self.meter_conn.record_metering_data(meter)

    def publish_events(self, context, events):
        if not isinstance(events, list):
            events = [events]

        self.event_conn.record_events(events)
