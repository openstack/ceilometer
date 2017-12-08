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

from tempest import config
from tempest.lib.common.utils import data_utils
from tempest.lib import exceptions as lib_exc
import tempest.test

from ceilometer.tests.tempest.aodh.service import client

CONF = config.CONF


class BaseAlarmingTest(tempest.test.BaseTestCase):
    """Base test case class for all Alarming API tests."""

    credentials = ['primary']
    client_manager = client.Manager

    @classmethod
    def skip_checks(cls):
        super(BaseAlarmingTest, cls).skip_checks()
        if not CONF.service_available.aodh_plugin:
            raise cls.skipException("Aodh support is required")

    @classmethod
    def setup_clients(cls):
        super(BaseAlarmingTest, cls).setup_clients()
        cls.alarming_client = cls.os_primary.alarming_client

    @classmethod
    def resource_setup(cls):
        super(BaseAlarmingTest, cls).resource_setup()
        cls.alarm_ids = []

    @classmethod
    def create_alarm(cls, **kwargs):
        body = cls.alarming_client.create_alarm(
            name=data_utils.rand_name('telemetry_alarm'),
            type='threshold', **kwargs)
        cls.alarm_ids.append(body['alarm_id'])
        return body

    @staticmethod
    def cleanup_resources(method, list_of_ids):
        for resource_id in list_of_ids:
            try:
                method(resource_id)
            except lib_exc.NotFound:
                pass

    @classmethod
    def resource_cleanup(cls):
        cls.cleanup_resources(cls.alarming_client.delete_alarm, cls.alarm_ids)
        super(BaseAlarmingTest, cls).resource_cleanup()
