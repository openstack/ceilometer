#
# Copyright 2013-2014 eNovance
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
from unittest import mock

from ceilometer import middleware
from ceilometer import service
from ceilometer.tests import base


HTTP_REQUEST = {
    'ctxt': {'auth_token': '3d8b13de1b7d499587dfc69b77dc09c2',
             'is_admin': True,
             'project_id': '7c150a59fe714e6f9263774af9688f0e',
             'quota_class': None,
             'read_deleted': 'no',
             'remote_address': '10.0.2.15',
             'request_id': 'req-d68b36e0-9233-467f-9afb-d81435d64d66',
             'roles': ['admin'],
             'timestamp': '2012-05-08T20:23:41.425105',
             'user_id': '1e3ce043029547f1a61c1996d1a531a2'},
    'event_type': 'http.request',
    'payload': {'request': {'HTTP_X_FOOBAR': 'foobaz',
                            'HTTP_X_USER_ID': 'jd-x32',
                            'HTTP_X_PROJECT_ID': 'project-id',
                            'HTTP_X_SERVICE_NAME': 'nova'}},
    'priority': 'INFO',
    'publisher_id': 'compute.vagrant-precise',
    'metadata': {'message_id': 'dae6f69c-00e0-41c0-b371-41ec3b7f4451',
                 'timestamp': '2012-05-08 20:23:48.028195'},
}

HTTP_RESPONSE = {
    'ctxt': {'auth_token': '3d8b13de1b7d499587dfc69b77dc09c2',
             'is_admin': True,
             'project_id': '7c150a59fe714e6f9263774af9688f0e',
             'quota_class': None,
             'read_deleted': 'no',
             'remote_address': '10.0.2.15',
             'request_id': 'req-d68b36e0-9233-467f-9afb-d81435d64d66',
             'roles': ['admin'],
             'timestamp': '2012-05-08T20:23:41.425105',
             'user_id': '1e3ce043029547f1a61c1996d1a531a2'},
    'event_type': 'http.response',
    'payload': {'request': {'HTTP_X_FOOBAR': 'foobaz',
                            'HTTP_X_USER_ID': 'jd-x32',
                            'HTTP_X_PROJECT_ID': 'project-id',
                            'HTTP_X_SERVICE_NAME': 'nova'},
                'response': {'status': '200 OK'}},
    'priority': 'INFO',
    'publisher_id': 'compute.vagrant-precise',
    'metadata': {'message_id': 'dae6f69c-00e0-41c0-b371-41ec3b7f4451',
                 'timestamp': '2012-05-08 20:23:48.028195'},
}


class TestNotifications(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.CONF = service.prepare_service([], [])
        self.setup_messaging(self.CONF)

    def test_process_request_notification(self):
        sample = list(middleware.HTTPRequest(
            mock.Mock(), mock.Mock()).build_sample(HTTP_REQUEST))[0]
        self.assertEqual(HTTP_REQUEST['payload']['request']['HTTP_X_USER_ID'],
                         sample.user_id)
        self.assertEqual(HTTP_REQUEST['payload']['request']
                         ['HTTP_X_PROJECT_ID'], sample.project_id)
        self.assertEqual(HTTP_REQUEST['payload']['request']
                         ['HTTP_X_SERVICE_NAME'], sample.resource_id)
        self.assertEqual(1, sample.volume)

    def test_process_response_notification(self):
        sample = list(middleware.HTTPResponse(
            mock.Mock(), mock.Mock()).build_sample(HTTP_RESPONSE))[0]
        self.assertEqual(HTTP_RESPONSE['payload']['request']['HTTP_X_USER_ID'],
                         sample.user_id)
        self.assertEqual(HTTP_RESPONSE['payload']['request']
                         ['HTTP_X_PROJECT_ID'], sample.project_id)
        self.assertEqual(HTTP_RESPONSE['payload']['request']
                         ['HTTP_X_SERVICE_NAME'], sample.resource_id)
        self.assertEqual(1, sample.volume)
