# Author: Swann Croiset <swann.croiset@bull.net>
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

from oslo.config import cfg

from ceilometer.openstack.common import test
from ceilometer.orchestration import notifications
from ceilometer import sample

NOW = datetime.datetime.isoformat(datetime.datetime.utcnow())

TENANT_ID = u'4c35985848bf4419b3f3d52c22e5792d'
STACK_NAME = u'AS1-ASGroup-53sqbo7sor7i'
STACK_ID = u'cb4a6fd1-1f5d-4002-ae91-9b91573cfb03'
USER_NAME = u'demo'
USER_ID = u'2e61f25ec63a4f6c954a6245421448a4'
TRUSTOR_ID = u'foo-Trustor-Id'

STACK_ARN = u'arn:openstack:heat::%s:stacks/%s/%s' % (TENANT_ID,
                                                      STACK_NAME,
                                                      STACK_ID)


CONF = cfg.CONF
CONF.set_override('use_stderr', True)

from ceilometer.openstack.common import log
LOG = log.getLogger(__name__)


def stack_notification_for(operation, use_trust=None):

    if use_trust:
        trust_id = 'footrust'
        trustor_id = TRUSTOR_ID
    else:
        trust_id = None
        trustor_id = None

    return {
        u'event_type': '%s.stack.%s.end' % (notifications.SERVICE,
                                            operation),
        u'_context_roles': [
            u'Member',
        ],
        u'_context_request_id': u'req-cf24cf30-af35-4a47-ae29-e74d75ebc6de',
        u'_context_auth_url': u'http://0.1.0.1:1010/v2.0',
        u'timestamp': NOW,
        u'_unique_id': u'1afb4283660f410c802af4d5992a39f2',
        u'_context_tenant_id': TENANT_ID,
        u'payload': {
            u'state_reason': u'Stack create completed successfully',
            u'user_id': USER_NAME,
            u'stack_identity': STACK_ARN,
            u'stack_name': STACK_NAME,
            u'tenant_id': TENANT_ID,
            u'create_at': u'2014-01-27T13:13:19Z',
            u'state': u'CREATE_COMPLETE'
        },
        u'_context_username': USER_NAME,
        u'_context_auth_token': u'MIISAwYJKoZIhvcNAQcCoII...',
        u'_context_password': u'password',
        u'_context_user_id': USER_ID,
        u'_context_trustor_user_id': trustor_id,
        u'_context_aws_creds': None,
        u'_context_show_deleted': False,
        u'_context_tenant': USER_NAME,
        u'_context_trust_id': trust_id,
        u'priority': u'INFO',
        u'_context_is_admin': False,
        u'_context_user': USER_NAME,
        u'publisher_id': u'orchestration.node-n5x66lxdy67d',
        u'message_id': u'ef921faa-7f7b-4854-8b86-a424ab93c96e',
    }


class TestNotification(test.BaseTestCase):

    def _verify_common_sample(self, s, name, volume):
        self.assertIsNotNone(s)
        self.assertEqual(s.name, 'stack.%s' % name)
        self.assertEqual(s.timestamp, NOW)
        self.assertEqual(s.type, sample.TYPE_DELTA)
        self.assertEqual(s.project_id, TENANT_ID)
        self.assertEqual(s.resource_id, STACK_ARN)
        metadata = s.resource_metadata
        self.assertEqual(metadata.get('host'),
                         u'orchestration.node-n5x66lxdy67d')

    def _test_operation(self, operation, trust=None):
        notif = stack_notification_for(operation, trust)
        handler = notifications.StackCRUD()
        data = list(handler.process_notification(notif))
        self.assertEqual(len(data), 1)
        if trust:
            self.assertEqual(data[0].user_id, TRUSTOR_ID)
        else:
            self.assertEqual(data[0].user_id, USER_ID)
        self._verify_common_sample(data[0], operation, 1)

    def test_create(self):
        self._test_operation('create')

    def test_create_trust(self):
        self._test_operation('create', trust=True)

    def test_update(self):
        self._test_operation('update')

    def test_delete(self):
        self._test_operation('delete')

    def test_resume(self):
        self._test_operation('resume')

    def test_suspend(self):
        self._test_operation('suspend')
