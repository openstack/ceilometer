#
# Copyright 2015 Hewlett-Packard Company
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

import datetime
from unittest import mock

from oslotest import base

from ceilometer import monasca_opts
from ceilometer.publisher import monasca_data_filter as mdf
from ceilometer import sample
from ceilometer import service


class TestMonUtils(base.BaseTestCase):
    def setUp(self):
        super(TestMonUtils, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.CONF.register_opts(list(monasca_opts.OPTS),
                                'monasca')
        self._field_mappings = {
            'dimensions': ['resource_id',
                           'project_id',
                           'user_id',
                           'geolocation',
                           'region',
                           'source',
                           'availability_zone'],

            'metadata': {
                'common': ['event_type',
                           'audit_period_beginning',
                           'audit_period_ending'],
                'image': ['size', 'status', 'image_meta.base_url',
                          'image_meta.base_url2', 'image_meta.base_url3',
                          'image_meta.base_url4'],
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
        self._field_mappings_cinder = {
            'dimensions': ['resource_id',
                           'project_id',
                           'user_id',
                           'geolocation',
                           'region',
                           'source',
                           'availability_zone'],

            'metadata': {
                'common': ['event_type',
                           'audit_period_beginning',
                           'audit_period_ending',
                           'arbitrary_new_field'],
                'volume.create.end':
                    ['size', 'status',
                     {'metering.prn_name':
                      "$.metadata[?(@.key = 'metering.prn_name')].value"},
                     {'metering.prn_type':
                      "$.metadata[?(@.key = 'metering.prn_type')].value"},
                     'volume_type', 'created_at',
                     'host'],
                'volume': ['status'],
                'volume.size': ['status'],
            }
        }

        self._field_mappings_bad_format = {
            'dimensions': ['resource_id',
                           'project_id',
                           'user_id',
                           'geolocation',
                           'region',
                           'source',
                           'availability_zone'],

            'metadata': {
                'common': ['event_type',
                           'audit_period_beginning',
                           'audit_period_ending',
                           'arbitrary_new_field'],
                'volume.create.end':
                    ['size', 'status',
                     {'metering.prn_name':
                      "$.metadata[?(@.key = 'metering.prn_name')].value",
                      'metering.prn_type':
                      "$.metadata[?(@.key = 'metering.prn_type')].value"},
                     'volume_type', 'created_at',
                     'host'],
                'volume': ['status'],
                'volume.size': ['status'],
            }
        }

    def test_process_sample(self):
        s = sample.Sample(
            name='test',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        )

        to_patch = ("ceilometer.publisher.monasca_data_filter."
                    "MonascaDataFilter._get_mapping")
        with mock.patch(to_patch, side_effect=[self._field_mappings]):
            data_filter = mdf.MonascaDataFilter(self.CONF)
            r = data_filter.process_sample_for_monasca(s)

            self.assertEqual(s.name, r['name'])
            self.assertIsNotNone(r.get('dimensions'))
            self.assertIsNotNone(r.get('value_meta'))
            self.assertIsNotNone(r.get('value'))
            self.assertEqual(s.user_id, r['dimensions'].get('user_id'))
            self.assertEqual(s.project_id, r['dimensions'].get('project_id'))
            self.assertEqual(s.resource_id, r['dimensions'].get('resource_id'))
            # 2015-04-07T20:07:06.156986 compare upto millisec
            monasca_ts = datetime.datetime.utcfromtimestamp(
                r['timestamp'] / 1000.0).isoformat()[:23]
            self.assertEqual(s.timestamp[:23], monasca_ts)

    def test_process_sample_field_mappings(self):
        s = sample.Sample(
            name='test',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        )

        field_map = self._field_mappings
        field_map['dimensions'].remove('project_id')
        field_map['dimensions'].remove('user_id')

        to_patch = ("ceilometer.publisher.monasca_data_filter."
                    "MonascaDataFilter._get_mapping")
        with mock.patch(to_patch, side_effect=[field_map]):
            data_filter = mdf.MonascaDataFilter(self.CONF)
            r = data_filter.process_sample_for_monasca(s)

            self.assertIsNone(r['dimensions'].get('project_id'))
            self.assertIsNone(r['dimensions'].get('user_id'))

    def convert_dict_to_list(self, dct, prefix=None, outlst={}):
        prefix = prefix + '.' if prefix else ""
        for k, v in dct.items():
            if type(v) is dict:
                self.convert_dict_to_list(v, prefix + k, outlst)
            else:
                if v is not None:
                    outlst[prefix + k] = v
                else:
                    outlst[prefix + k] = 'None'
        return outlst

    def test_process_sample_metadata(self):
        s = sample.Sample(
            name='image',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'event_type': 'notification',
                               'status': 'active',
                               'image_meta': {'base_url': 'http://image.url',
                                              'base_url2': '',
                                              'base_url3': None},
                               'size': 1500},
        )

        to_patch = ("ceilometer.publisher.monasca_data_filter."
                    "MonascaDataFilter._get_mapping")
        with mock.patch(to_patch, side_effect=[self._field_mappings]):
            data_filter = mdf.MonascaDataFilter(self.CONF)
            r = data_filter.process_sample_for_monasca(s)
            self.assertEqual(s.name, r['name'])
            self.assertIsNotNone(r.get('value_meta'))
            self.assertTrue(set(self.convert_dict_to_list(
                s.resource_metadata
            ).items()).issubset(set(r['value_meta'].items())))

    def test_process_sample_metadata_with_empty_data(self):
        s = sample.Sample(
            name='image',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            source='',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'event_type': 'notification',
                               'status': 'active',
                               'image_meta': {'base_url': 'http://image.url',
                                              'base_url2': '',
                                              'base_url3': None},
                               'size': 0},
        )

        to_patch = ("ceilometer.publisher.monasca_data_filter."
                    "MonascaDataFilter._get_mapping")
        with mock.patch(to_patch, side_effect=[self._field_mappings]):
            data_filter = mdf.MonascaDataFilter(self.CONF)
            r = data_filter.process_sample_for_monasca(s)

            self.assertEqual(s.name, r['name'])
            self.assertIsNotNone(r.get('value_meta'))
            self.assertEqual(s.source, r['dimensions']['source'])
            self.assertTrue(set(self.convert_dict_to_list(
                s.resource_metadata
            ).items()).issubset(set(r['value_meta'].items())))

    def test_process_sample_metadata_with_extendedKey(self):
        s = sample.Sample(
            name='image',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            source='',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'event_type': 'notification',
                               'status': 'active',
                               'image_meta': {'base_url': 'http://image.url',
                                              'base_url2': '',
                                              'base_url3': None},
                               'size': 0},
        )

        to_patch = ("ceilometer.publisher.monasca_data_filter."
                    "MonascaDataFilter._get_mapping")
        with mock.patch(to_patch, side_effect=[self._field_mappings]):
            data_filter = mdf.MonascaDataFilter(self.CONF)
            r = data_filter.process_sample_for_monasca(s)

            self.assertEqual(s.name, r['name'])
            self.assertIsNotNone(r.get('value_meta'))
            self.assertTrue(set(self.convert_dict_to_list(
                s.resource_metadata
            ).items()).issubset(set(r['value_meta'].items())))
            self.assertEqual(r.get('value_meta')['image_meta.base_url'],
                             s.resource_metadata.get('image_meta')
                             ['base_url'])
            self.assertEqual(r.get('value_meta')['image_meta.base_url2'],
                             s.resource_metadata.get('image_meta')
                             ['base_url2'])
            self.assertEqual(r.get('value_meta')['image_meta.base_url3'],
                             str(s.resource_metadata.get('image_meta')
                                 ['base_url3']))
            self.assertEqual(r.get('value_meta')['image_meta.base_url4'],
                             'None')

    def test_process_sample_metadata_with_jsonpath(self):
        """Test meter sample in a format produced by cinder."""
        s = sample.Sample(
            name='volume.create.end',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            source='',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'event_type': 'volume.create.end',
                               'status': 'available',
                               'volume_type': None,
                               # 'created_at': '2017-03-21T21:05:44+00:00',
                               'host': 'testhost',
                               # this "value: , key: " format is
                               # how cinder reports metadata
                               'metadata':
                                   [{'value': 'aaa0001',
                                     'key': 'metering.prn_name'},
                                    {'value': 'Cust001',
                                     'key': 'metering.prn_type'}],
                               'size': 0},
        )

        to_patch = ("ceilometer.publisher.monasca_data_filter."
                    "MonascaDataFilter._get_mapping")
        # use the cinder specific mapping
        with mock.patch(to_patch, side_effect=[self._field_mappings_cinder]):
            data_filter = mdf.MonascaDataFilter(self.CONF)
            r = data_filter.process_sample_for_monasca(s)

            self.assertEqual(s.name, r['name'])
            self.assertIsNotNone(r.get('value_meta'))
            # Using convert_dict_to_list is too simplistic for this
            self.assertEqual(r.get('value_meta')['event_type'],
                             s.resource_metadata.get('event_type'),
                             "Failed to match common element.")
            self.assertEqual(r.get('value_meta')['host'],
                             s.resource_metadata.get('host'),
                             "Failed to match meter specific element.")
            self.assertEqual(r.get('value_meta')['size'],
                             s.resource_metadata.get('size'),
                             "Unable to handle an int.")
            self.assertEqual(r.get('value_meta')['metering.prn_name'],
                             'aaa0001',
                             "Failed to extract a value "
                             "using specified jsonpath.")

    def test_process_sample_metadata_with_jsonpath_nomatch(self):
        """Test meter sample in a format produced by cinder.

        Behavior when no matching element is found for the specified jsonpath
        """

        s = sample.Sample(
            name='volume.create.end',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            source='',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'event_type': 'volume.create.end',
                               'status': 'available',
                               'volume_type': None,
                               # 'created_at': '2017-03-21T21:05:44+00:00',
                               'host': 'testhost',
                               'metadata': [{'value': 'aaa0001',
                                             'key': 'metering.THISWONTMATCH'}],
                               'size': 0},
        )

        to_patch = ("ceilometer.publisher.monasca_data_filter."
                    "MonascaDataFilter._get_mapping")
        # use the cinder specific mapping
        with mock.patch(to_patch, side_effect=[self._field_mappings_cinder]):
            data_filter = mdf.MonascaDataFilter(self.CONF)
            r = data_filter.process_sample_for_monasca(s)

            self.assertEqual(s.name, r['name'])
            self.assertIsNotNone(r.get('value_meta'))
            # Using convert_dict_to_list is too simplistic for this
            self.assertEqual(r.get('value_meta')['event_type'],
                             s.resource_metadata.get('event_type'),
                             "Failed to match common element.")
            self.assertEqual(r.get('value_meta')['host'],
                             s.resource_metadata.get('host'),
                             "Failed to match meter specific element.")
            self.assertEqual(r.get('value_meta')['size'],
                             s.resource_metadata.get('size'),
                             "Unable to handle an int.")
            self.assertEqual(r.get('value_meta')['metering.prn_name'],
                             'None', "This metadata should fail to match "
                                     "and then return 'None'.")

    def test_process_sample_metadata_with_jsonpath_value_not_str(self):
        """Test where jsonpath is used but result is not a simple string"""

        s = sample.Sample(
            name='volume.create.end',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            source='',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'event_type': 'volume.create.end',
                               'status': 'available',
                               'volume_type': None,
                               # 'created_at': '2017-03-21T21:05:44+00:00',
                               'host': 'testhost',
                               'metadata': [{'value': ['aaa0001', 'bbbb002'],
                                             'key': 'metering.prn_name'}],
                               'size': 0},
        )

        to_patch = ("ceilometer.publisher.monasca_data_filter."
                    "MonascaDataFilter._get_mapping")
        # use the cinder specific mapping
        with mock.patch(to_patch, side_effect=[self._field_mappings_cinder]):
            data_filter = mdf.MonascaDataFilter(self.CONF)
            try:
                # Don't assign to a variable, this should raise
                data_filter.process_sample_for_monasca(s)
            except mdf.CeiloscaMappingDefinitionException as e:
                self.assertEqual(
                    'Metadata format mismatch, value should be '
                    'a simple string. [\'aaa0001\', \'bbbb002\']',
                    e.message)

    def test_process_sample_metadata_with_jsonpath_value_is_int(self):
        """Test meter sample where jsonpath result is an int."""

        s = sample.Sample(
            name='volume.create.end',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            source='',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'event_type': 'volume.create.end',
                               'status': 'available',
                               'volume_type': None,
                               # 'created_at': '2017-03-21T21:05:44+00:00',
                               'host': 'testhost',
                               'metadata': [{'value': 13,
                                             'key': 'metering.prn_name'}],
                               'size': 0},
        )

        to_patch = ("ceilometer.publisher.monasca_data_filter."
                    "MonascaDataFilter._get_mapping")
        # use the cinder specific mapping
        with mock.patch(to_patch, side_effect=[self._field_mappings_cinder]):
            data_filter = mdf.MonascaDataFilter(self.CONF)
            r = data_filter.process_sample_for_monasca(s)

            self.assertEqual(s.name, r['name'])
            self.assertIsNotNone(r.get('value_meta'))
            # Using convert_dict_to_list is too simplistic for this
            self.assertEqual(r.get('value_meta')['event_type'],
                             s.resource_metadata.get('event_type'),
                             "Failed to match common element.")
            self.assertEqual(r.get('value_meta')['host'],
                             s.resource_metadata.get('host'),
                             "Failed to match meter specific element.")
            self.assertEqual(r.get('value_meta')['size'],
                             s.resource_metadata.get('size'),
                             "Unable to handle an int.")
            self.assertEqual(r.get('value_meta')['metering.prn_name'],
                             13,
                             "Unable to handle an int "
                             "through the jsonpath processing")

    def test_process_sample_metadata_with_jsonpath_bad_format(self):
        """Test handling of definition that is not written correctly"""

        s = sample.Sample(
            name='volume.create.end',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            source='',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'event_type': 'volume.create.end',
                               'status': 'available',
                               'volume_type': None,
                               # 'created_at': '2017-03-21T21:05:44+00:00',
                               'host': 'testhost',
                               'metadata': [{'value': 13,
                                             'key': 'metering.prn_name'}],
                               'size': 0},
        )

        to_patch = ("ceilometer.publisher.monasca_data_filter."
                    "MonascaDataFilter._get_mapping")
        # use the bad mapping
        with mock.patch(to_patch,
                        side_effect=[self._field_mappings_bad_format]):
            data_filter = mdf.MonascaDataFilter(self.CONF)
            try:
                # Don't assign to a variable as this should raise
                data_filter.process_sample_for_monasca(s)
            except mdf.CeiloscaMappingDefinitionException as e:
                # Make sure we got the right kind of error
                # Cannot check the whole message text, as python
                # may reorder a dict when producing a string version
                self.assertIn(
                    'Field definition format mismatch, should '
                    'have only one key:value pair.',
                    e.message,
                    "Did raise exception but wrong message - %s" % e.message)
