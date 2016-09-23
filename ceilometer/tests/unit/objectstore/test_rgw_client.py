# Copyright (C) 2015 Reliance Jio Infocomm Ltd
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

import mock
from oslotest import base

from ceilometer.objectstore import rgw_client


RGW_ADMIN_BUCKETS = '''
[
  {
    "max_marker": "",
    "ver": 2001,
    "usage": {
      "rgw.main": {
        "size_kb_actual": 16000,
        "num_objects": 1000,
        "size_kb": 1000
      }
    },
    "bucket": "somefoo",
    "owner": "admin",
    "master_ver": 0,
    "mtime": 1420176126,
    "marker": "default.4126.1",
    "bucket_quota": {
      "max_objects": -1,
      "enabled": false,
      "max_size_kb": -1
    },
    "id": "default.4126.1",
    "pool": ".rgw.buckets",
    "index_pool": ".rgw.buckets.index"
  },
  {
    "max_marker": "",
    "ver": 3,
    "usage": {
      "rgw.main": {
        "size_kb_actual": 43,
        "num_objects": 1,
        "size_kb": 42
      }
    },
    "bucket": "somefoo31",
    "owner": "admin",
    "master_ver": 0,
    "mtime": 1420176134,
    "marker": "default.4126.5",
    "bucket_quota": {
      "max_objects": -1,
      "enabled": false,
      "max_size_kb": -1
    },
    "id": "default.4126.5",
    "pool": ".rgw.buckets",
    "index_pool": ".rgw.buckets.index"
  }
]'''

RGW_ADMIN_USAGE = '''
{ "entries": [
        { "owner": "5f7fe2d5352e466f948f49341e33d107",
          "buckets": [
                { "bucket": "",
                  "time": "2015-01-23 09:00:00.000000Z",
                  "epoch": 1422003600,
                  "categories": [
                        { "category": "list_buckets",
                          "bytes_sent": 46,
                          "bytes_received": 0,
                          "ops": 3,
                          "successful_ops": 3},
                        { "category": "stat_account",
                          "bytes_sent": 0,
                          "bytes_received": 0,
                          "ops": 1,
                          "successful_ops": 1}]},
                { "bucket": "foodsgh",
                  "time": "2015-01-23 09:00:00.000000Z",
                  "epoch": 1422003600,
                  "categories": [
                        { "category": "create_bucket",
                          "bytes_sent": 0,
                          "bytes_received": 0,
                          "ops": 1,
                          "successful_ops": 1},
                        { "category": "get_obj",
                          "bytes_sent": 0,
                          "bytes_received": 0,
                          "ops": 1,
                          "successful_ops": 0},
                        { "category": "put_obj",
                          "bytes_sent": 0,
                          "bytes_received": 238,
                          "ops": 1,
                          "successful_ops": 1}]}]}],
  "summary": [
        { "user": "5f7fe2d5352e466f948f49341e33d107",
          "categories": [
                { "category": "create_bucket",
                  "bytes_sent": 0,
                  "bytes_received": 0,
                  "ops": 1,
                  "successful_ops": 1},
                { "category": "get_obj",
                  "bytes_sent": 0,
                  "bytes_received": 0,
                  "ops": 1,
                  "successful_ops": 0},
                { "category": "list_buckets",
                  "bytes_sent": 46,
                  "bytes_received": 0,
                  "ops": 3,
                  "successful_ops": 3},
                { "category": "put_obj",
                  "bytes_sent": 0,
                  "bytes_received": 238,
                  "ops": 1,
                  "successful_ops": 1},
                { "category": "stat_account",
                  "bytes_sent": 0,
                  "bytes_received": 0,
                  "ops": 1,
                  "successful_ops": 1}],
          "total": { "bytes_sent": 46,
              "bytes_received": 238,
              "ops": 7,
              "successful_ops": 6}}]}
'''

buckets_json = json.loads(RGW_ADMIN_BUCKETS)
usage_json = json.loads(RGW_ADMIN_USAGE)


class TestRGWAdminClient(base.BaseTestCase):

    def setUp(self):
        super(TestRGWAdminClient, self).setUp()
        self.client = rgw_client.RGWAdminClient('http://127.0.0.1:8080/admin',
                                                'abcde', 'secret')
        self.get_resp = mock.MagicMock()
        self.get = mock.patch('requests.get',
                              return_value=self.get_resp).start()

    def test_make_request_exception(self):
        self.get_resp.status_code = 403
        self.assertRaises(rgw_client.RGWAdminAPIFailed,
                          self.client._make_request,
                          *('foo', {}))

    def test_make_request(self):
        self.get_resp.status_code = 200
        self.get_resp.json.return_value = buckets_json
        actual = self.client._make_request('foo', [])
        self.assertEqual(buckets_json, actual)

    def test_get_buckets(self):
        self.get_resp.status_code = 200
        self.get_resp.json.return_value = buckets_json
        actual = self.client.get_bucket('foo')
        bucket_list = [rgw_client.RGWAdminClient.Bucket('somefoo', 1000, 1000),
                       rgw_client.RGWAdminClient.Bucket('somefoo31', 1, 42),
                       ]
        expected = {'num_buckets': 2, 'size': 1042, 'num_objects': 1001,
                    'buckets': bucket_list}
        self.assertEqual(expected, actual)

    def test_get_usage(self):
        self.get_resp.status_code = 200
        self.get_resp.json.return_value = usage_json
        actual = self.client.get_usage('foo')
        expected = 7
        self.assertEqual(expected, actual)
