#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

# Change-Id: I14e16a1a7d9813b324ee40545c07f0e88fb637b7

import six
import testtools

from ceilometer.tests.tempest.api import base
from tempest import config
from tempest.lib.common.utils import data_utils
from tempest.lib import decorators
from tempest import test


CONF = config.CONF


class TelemetryNotificationAPITest(base.BaseTelemetryTest):
    @classmethod
    def skip_checks(cls):
        super(TelemetryNotificationAPITest, cls).skip_checks()

        if ("gnocchi" in CONF.service_available and
                CONF.service_available.gnocchi):
            skip_msg = ("%s skipped as gnocchi is enabled" %
                        cls.__name__)
            raise cls.skipException(skip_msg)

    @decorators.idempotent_id('d7f8c1c8-d470-4731-8604-315d3956caae')
    @test.services('compute')
    def test_check_nova_notification(self):

        body = self.create_server()

        query = ('resource', 'eq', body['id'])

        for metric in self.nova_notifications:
            self.await_samples(metric, query)

    @decorators.idempotent_id('c240457d-d943-439b-8aea-85e26d64fe8f')
    @test.services("image")
    @testtools.skipIf(not CONF.image_feature_enabled.api_v2,
                      "Glance api v2 is disabled")
    def test_check_glance_v2_notifications(self):
        body = self.create_image(self.image_client_v2, visibility='private')

        file_content = data_utils.random_bytes()
        image_file = six.BytesIO(file_content)
        self.image_client_v2.store_image_file(body['id'], image_file)
        self.image_client_v2.show_image_file(body['id'])

        query = 'resource', 'eq', body['id']

        for metric in self.glance_v2_notifications:
            self.await_samples(metric, query)


class TelemetryNotificationAdminAPITest(base.BaseTelemetryAdminTest):
    @classmethod
    def skip_checks(cls):
        super(TelemetryNotificationAdminAPITest, cls).skip_checks()

        if ("gnocchi" in CONF.service_available and
                CONF.service_available.gnocchi):
            skip_msg = ("%s skipped as gnocchi is enabled" %
                        cls.__name__)
            raise cls.skipException(skip_msg)

    @decorators.idempotent_id('29604198-8b45-4fc0-8af8-1cae4f94ebea')
    @test.services('compute')
    def test_check_nova_notification_event_and_meter(self):

        body = self.create_server()

        query = ('resource', 'eq', body['id'])
        for metric in self.nova_notifications:
            self.await_samples(metric, query)
