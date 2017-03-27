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
from oslo_config import cfg
from oslo_utils import fileutils
import six
from six.moves.urllib import parse as urlparse

from ceilometer.api import app
from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer import service
from ceilometer import storage

# TODO(chdent): For now only MongoDB is supported, because of easy
# database name handling and intentional focus on the API, not the
# data store.
ENGINES = ['mongodb']

# NOTE(chdent): Hack to restore semblance of global configuration to
# pass to the WSGI app used per test suite. LOAD_APP_KWARGS are the olso
# configuration, and the pecan application configuration of
# which the critical part is a reference to the current indexer.
LOAD_APP_KWARGS = None


def setup_app():
    global LOAD_APP_KWARGS
    return app.load_app(**LOAD_APP_KWARGS)


class ConfigFixture(fixture.GabbiFixture):
    """Establish the relevant configuration for a test run."""

    def start_fixture(self):
        """Set up config."""

        global LOAD_APP_KWARGS

        self.conf = None

        # Determine the database connection.
        db_url = os.environ.get('PIFPAF_URL', "sqlite://").replace(
            "mysql://", "mysql+pymysql://")
        if not db_url:
            raise case.SkipTest('No database connection configured')

        engine = urlparse.urlparse(db_url).scheme
        if engine not in ENGINES:
            raise case.SkipTest('Database engine not supported')

        self.conf = service.prepare_service([], [])

        content = ('{"default": ""}')
        if six.PY3:
            content = content.encode('utf-8')
        self.tempfile = fileutils.write_to_tempfile(content=content,
                                                    prefix='policy',
                                                    suffix='.json')

        self.conf.set_override("policy_file", self.tempfile,
                               group='oslo_policy')
        self.conf.set_override(
            'api_paste_config',
            os.path.abspath(
                'ceilometer/tests/functional/gabbi/gabbi_paste.ini')
        )

        # A special pipeline is required to use the direct publisher.
        self.conf.set_override(
            'pipeline_cfg_file',
            'ceilometer/tests/functional/gabbi_pipeline.yaml')

        database_name = '%s-%s' % (db_url, str(uuid.uuid4()))
        self.conf.set_override('connection', database_name, group='database')
        self.conf.set_override('metering_connection', '', group='database')

        self.conf.set_override('gnocchi_is_enabled', False, group='api')
        self.conf.set_override('aodh_is_enabled', False, group='api')
        self.conf.set_override('panko_is_enabled', False, group='api')

        LOAD_APP_KWARGS = {
            'conf': self.conf,
        }

    def stop_fixture(self):
        """Reset the config and remove data."""
        if self.conf:
            storage.get_connection_from_config(self.conf).clear()
            self.conf.reset()


class SampleDataFixture(fixture.GabbiFixture):
    """Instantiate some sample data for use in testing."""

    def start_fixture(self):
        """Create some samples."""
        global LOAD_APP_KWARGS
        conf = LOAD_APP_KWARGS['conf']
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


class CORSConfigFixture(fixture.GabbiFixture):
    """Inject mock configuration for the CORS middleware."""

    def start_fixture(self):
        # Here we monkeypatch GroupAttr.__getattr__, necessary because the
        # paste.ini method of initializing this middleware creates its own
        # ConfigOpts instance, bypassing the regular config fixture.

        def _mock_getattr(instance, key):
            if key != 'allowed_origin':
                return self._original_call_method(instance, key)
            return "http://valid.example.com"

        self._original_call_method = cfg.ConfigOpts.GroupAttr.__getattr__
        cfg.ConfigOpts.GroupAttr.__getattr__ = _mock_getattr

    def stop_fixture(self):
        """Remove the monkeypatch."""
        cfg.ConfigOpts.GroupAttr.__getattr__ = self._original_call_method
