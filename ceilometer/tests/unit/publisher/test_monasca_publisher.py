#
# Copyright 2015 Hewlett Packard
# (c) Copyright 2018 SUSE LLC
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
"""Tests for ceilometer/publisher/monasca.py"""

import datetime
import fixtures
import time
from unittest import mock

from oslotest import base

from ceilometer import monasca_client as mon_client
from ceilometer.publisher import monasca as mon_publisher
from ceilometer import sample
from ceilometer import service


class FakeResponse(object):
    def __init__(self, status_code):
        self.status_code = status_code


class TestMonascaPublisher(base.BaseTestCase):

    test_data = [
        sample.Sample(
            name='test',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='test2',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='test2',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
    ]

    field_mappings = {
        'dimensions': ['resource_id',
                       'project_id',
                       'user_id',
                       'geolocation',
                       'region',
                       'availability_zone'],

        'metadata': {
            'common': ['event_type',
                       'audit_period_beginning',
                       'audit_period_ending'],
            'image': ['size', 'status'],
            'image.delete': ['size', 'status'],
            'image.size': ['size', 'status'],
            'image.update': ['size', 'status'],
            'image.upload': ['size', 'status'],
            'instance': ['state', 'state_description'],
            'snapshot': ['status'],
            'snapshot.size': ['status'],
            'volume': ['status'],
            'volume.size': ['status'],
        }
    }

    @staticmethod
    def create_side_effect(exception_type, test_exception):
        def side_effect(*args, **kwargs):
            if test_exception.pop():
                raise exception_type
            else:
                return FakeResponse(204)
        return side_effect

    def setUp(self):
        super(TestMonascaPublisher, self).setUp()

        self.CONF = service.prepare_service([], [])
        self.parsed_url = mock.MagicMock()

    def tearDown(self):
        # For some reason, cfg.CONF is registered a required option named
        # auth_url after these tests run, which occasionally blocks test
        # case test_event_pipeline_endpoint_requeue_on_failure, so we
        # unregister it here.
        self.CONF.reset()
        # self.CONF.unregister_opt(cfg.StrOpt('service_auth_url'),
        #                          group='monasca')
        super(TestMonascaPublisher, self).tearDown()

    @mock.patch("ceilometer.publisher.monasca_data_filter."
                "MonascaDataFilter._get_mapping",
                side_effect=[field_mappings])
    def test_publisher_publish(self, mapping_patch):
        self.CONF.set_override('batch_mode', False, group='monasca')
        publisher = mon_publisher.MonascaPublisher(self.CONF, self.parsed_url)
        publisher.mon_client = mock.MagicMock()

        with mock.patch.object(publisher.mon_client,
                               'metrics_create') as mock_create:
            mock_create.return_value = FakeResponse(204)
            publisher.publish_samples(self.test_data)
            self.assertEqual(3, mock_create.call_count)
            self.assertEqual(1, mapping_patch.called)

    @mock.patch("ceilometer.publisher.monasca_data_filter."
                "MonascaDataFilter._get_mapping",
                side_effect=[field_mappings])
    def test_publisher_batch(self, mapping_patch):
        self.CONF.set_override('batch_mode', True, group='monasca')
        self.CONF.set_override('batch_count', 3, group='monasca')
        self.CONF.set_override('batch_polling_interval', 1, group='monasca')

        publisher = mon_publisher.MonascaPublisher(self.CONF, self.parsed_url)
        publisher.mon_client = mock.MagicMock()
        with mock.patch.object(publisher.mon_client,
                               'metrics_create') as mock_create:
            mock_create.return_value = FakeResponse(204)
            publisher.publish_samples(self.test_data)
            time.sleep(10)
            self.assertEqual(1, mock_create.call_count)
            self.assertEqual(1, mapping_patch.called)

    @mock.patch("ceilometer.publisher.monasca_data_filter."
                "MonascaDataFilter._get_mapping",
                side_effect=[field_mappings])
    def test_publisher_batch_retry(self, mapping_patch):
        self.CONF.set_override('batch_mode', True, group='monasca')
        self.CONF.set_override('batch_count', 3, group='monasca')
        self.CONF.set_override('batch_polling_interval', 1, group='monasca')
        self.CONF.set_override('retry_on_failure', True, group='monasca')
        # Constant in code for @periodicals, can't override
        # self.CONF.set_override('retry_interval', 2, group='monasca')
        self.CONF.set_override('batch_max_retries', 1, group='monasca')

        publisher = mon_publisher.MonascaPublisher(self.CONF, self.parsed_url)
        publisher.mon_client = mock.MagicMock()
        with mock.patch.object(publisher.mon_client,
                               'metrics_create') as mock_create:
            raise_http_error = [False, False, False, True]
            mock_create.side_effect = self.create_side_effect(
                mon_client.MonascaServiceException,
                raise_http_error)
            publisher.publish_samples(self.test_data)
            time.sleep(60)
            self.assertEqual(4, mock_create.call_count)
            self.assertEqual(1, mapping_patch.called)

    @mock.patch("ceilometer.publisher.monasca_data_filter."
                "MonascaDataFilter._get_mapping",
                side_effect=[field_mappings])
    def test_publisher_archival_on_failure(self, mapping_patch):
        self.CONF.set_override('archive_on_failure', True, group='monasca')
        self.CONF.set_override('batch_mode', False, group='monasca')
        self.fake_publisher = mock.Mock()

        self.useFixture(fixtures.MockPatch(
            'ceilometer.publisher.file.FilePublisher',
            return_value=self.fake_publisher))

        publisher = mon_publisher.MonascaPublisher(self.CONF,
                                                   self.parsed_url)
        publisher.mon_client = mock.MagicMock()

        with mock.patch.object(publisher.mon_client,
                               'metrics_create') as mock_create:
            mock_create.side_effect = Exception
            metrics_archiver = self.fake_publisher.publish_samples
            publisher.publish_samples(self.test_data)
            self.assertEqual(1, metrics_archiver.called)
            self.assertEqual(3, metrics_archiver.call_count)
