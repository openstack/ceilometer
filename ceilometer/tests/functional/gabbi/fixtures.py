#
# Copyright 2015 Red Hat. All Rights Reserved.
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

"""Fixtures used during Gabbi-based test runs."""

import datetime
import os
import random
from unittest import case
import uuid

from gabbi import fixture
from oslo_config import fixture as fixture_config
from oslo_policy import opts

from ceilometer.event.storage import models
from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer import storage


# TODO(chdent): For now only MongoDB is supported, because of easy
# database name handling and intentional focus on the API, not the
# data store.
ENGINES = ['MONGODB']


class ConfigFixture(fixture.GabbiFixture):
    """Establish the relevant configuration for a test run."""

    def start_fixture(self):
        """Set up config."""

        self.conf = None

        # Determine the database connection.
        db_url = None
        for engine in ENGINES:
            try:
                db_url = os.environ['CEILOMETER_TEST_%s_URL' % engine]
            except KeyError:
                pass
        if db_url is None:
            raise case.SkipTest('No database connection configured')

        conf = fixture_config.Config().conf
        self.conf = conf
        self.conf([], project='ceilometer', validate_default_values=True)
        opts.set_defaults(self.conf)
        conf.import_group('api', 'ceilometer.api.controllers.v2.root')
        conf.import_opt('store_events', 'ceilometer.notification',
                        group='notification')
        conf.set_override('policy_file',
                          os.path.abspath('etc/ceilometer/policy.json'),
                          group='oslo_policy')

        # A special pipeline is required to use the direct publisher.
        conf.set_override('pipeline_cfg_file',
                          'etc/ceilometer/gabbi_pipeline.yaml')

        database_name = '%s-%s' % (db_url, str(uuid.uuid4()))
        conf.set_override('connection', database_name, group='database')
        conf.set_override('metering_connection', '', group='database')
        conf.set_override('event_connection', '', group='database')
        conf.set_override('alarm_connection', '', group='database')

        conf.set_override('pecan_debug', True, group='api')
        conf.set_override('gnocchi_is_enabled', False, group='api')
        conf.set_override('aodh_is_enabled', False, group='api')

        conf.set_override('store_events', True, group='notification')

    def stop_fixture(self):
        """Reset the config and remove data."""
        if self.conf:
            storage.get_connection_from_config(self.conf).clear()
            self.conf.reset()


class SampleDataFixture(fixture.GabbiFixture):
    """Instantiate some sample data for use in testing."""

    def start_fixture(self):
        """Create some samples."""
        conf = fixture_config.Config().conf
        self.conn = storage.get_connection_from_config(conf)
        timestamp = datetime.datetime.utcnow()
        project_id = str(uuid.uuid4())
        self.source = str(uuid.uuid4())
        resource_metadata = {'farmed_by': 'nancy'}

        for name in ['cow', 'pig', 'sheep']:
            resource_metadata.update({'breed': name}),
            c = sample.Sample(name='livestock',
                              type='gauge',
                              unit='head',
                              volume=int(10 * random.random()),
                              user_id='farmerjon',
                              project_id=project_id,
                              resource_id=project_id,
                              timestamp=timestamp,
                              resource_metadata=resource_metadata,
                              source=self.source)
            data = utils.meter_message_from_counter(
                c, conf.publisher.telemetry_secret)
            self.conn.record_metering_data(data)

    def stop_fixture(self):
        """Destroy the samples."""
        # NOTE(chdent): print here for sake of info during testing.
        # This will go away eventually.
        print('resource',
              self.conn.db.resource.remove({'source': self.source}))
        print('meter', self.conn.db.meter.remove({'source': self.source}))


class EventDataFixture(fixture.GabbiFixture):
    """Instantiate some sample event data for use in testing."""

    def start_fixture(self):
        """Create some events."""
        conf = fixture_config.Config().conf
        self.conn = storage.get_connection_from_config(conf, 'event')
        events = []
        name_list = ['chocolate.chip', 'peanut.butter', 'sugar']
        for ix, name in enumerate(name_list):
            timestamp = datetime.datetime.utcnow()
            message_id = 'fea1b15a-1d47-4175-85a5-a4bb2c72924{}'.format(ix)
            traits = [models.Trait('type', 1, name),
                      models.Trait('ate', 2, ix)]
            event = models.Event(message_id,
                                 'cookies_{}'.format(name),
                                 timestamp,
                                 traits, {'nested': {'inside': 'value'}})
            events.append(event)
        self.conn.record_events(events)

    def stop_fixture(self):
        """Destroy the events."""
        self.conn.db.event.remove({'event_type': '/^cookies_/'})
