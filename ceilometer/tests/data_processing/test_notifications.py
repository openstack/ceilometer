# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime

import mock
from oslo.config import cfg
from oslotest import base

from ceilometer.data_processing import notifications
from ceilometer.openstack.common import log
from ceilometer import sample

NOW = datetime.datetime.isoformat(datetime.datetime.utcnow())

TENANT_ID = u'4c35985848bf4419b3f3d52c22e5792d'
CLUSTER_NAME = u'AS1-ASGroup-53sqbo7sor7i'
CLUSTER_ID = u'cb4a6fd1-1f5d-4002-ae91-9b91573cfb03'
USER_NAME = u'demo'
USER_ID = u'2e61f25ec63a4f6c954a6245421448a4'
CLUSTER_STATUS = u'Active'
PROJECT_ID = TENANT_ID
RESOURCE_ID = CLUSTER_ID
PUBLISHER_ID = u'data_processing.node-n5x66lxdy67d'


CONF = cfg.CONF
CONF.set_override('use_stderr', True)

LOG = log.getLogger(__name__)


def _dp_notification_for(operation):

    return {
        u'event_type': '%s.cluster.%s' % (notifications.SERVICE,
                                          operation),
        u'_context_roles': [
            u'Member',
        ],
        u'_context_auth_uri': u'http://0.1.0.1:1010/v2.0',
        u'timestamp': NOW,
        u'_context_tenant_id': TENANT_ID,
        u'payload': {
            u'cluster_id': CLUSTER_ID,
            u'cluster_name': CLUSTER_NAME,
            u'cluster_status': CLUSTER_STATUS,
            u'project_id': TENANT_ID,
            u'user_id': USER_ID,
        },
        u'_context_username': USER_NAME,
        u'_context_token': u'MIISAwYJKoZIhvcNAQcCoII...',
        u'_context_user_id': USER_ID,
        u'_context_tenant_name': USER_NAME,
        u'priority': u'INFO',
        u'_context_is_admin': False,
        u'publisher_id': PUBLISHER_ID,
        u'message_id': u'ef921faa-7f7b-4854-8b86-a424ab93c96e',
    }


class TestNotification(base.BaseTestCase):
    def _verify_common_sample(self, actual, operation):
        self.assertIsNotNone(actual)
        self.assertEqual('cluster.%s' % operation, actual.name)
        self.assertEqual(NOW, actual.timestamp)
        self.assertEqual(sample.TYPE_DELTA, actual.type)
        self.assertEqual(PROJECT_ID, actual.project_id)
        self.assertEqual(RESOURCE_ID, actual.resource_id)
        self.assertEqual(USER_ID, actual.user_id)
        metadata = actual.resource_metadata
        self.assertEqual(PUBLISHER_ID, metadata.get('host'))

    def _test_operation(self, operation):
        notif = _dp_notification_for(operation)
        handler = notifications.DataProcessing(mock.Mock())
        data = list(handler.process_notification(notif))
        self.assertEqual(1, len(data))
        self._verify_common_sample(data[0], operation)

    def test_create(self):
        self._test_operation('create')

    def test_update(self):
        self._test_operation('update')

    def test_delete(self):
        self._test_operation('delete')
