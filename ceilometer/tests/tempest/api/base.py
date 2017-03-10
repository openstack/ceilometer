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

import time

from oslo_utils import timeutils
from tempest.common import compute
from tempest import config
from tempest.lib.common.utils import data_utils
from tempest.lib import exceptions as lib_exc
import tempest.test

from ceilometer.tests.tempest.service import client


CONF = config.CONF


class ClientManager(client.Manager):

    load_clients = [
        'servers_client',
        'compute_networks_client',
        'compute_floating_ips_client',
        'flavors_client',
        'image_client_v2',
        'telemetry_client',
    ]


class BaseTelemetryTest(tempest.test.BaseTestCase):

    """Base test case class for all Telemetry API tests."""

    credentials = ['primary']
    client_manager = ClientManager

    @classmethod
    def skip_checks(cls):
        super(BaseTelemetryTest, cls).skip_checks()
        if (not CONF.service_available.ceilometer or
                not CONF.telemetry.deprecated_api_enabled):
            raise cls.skipException("Ceilometer API support is required")

    @classmethod
    def setup_credentials(cls):
        cls.set_network_resources()
        super(BaseTelemetryTest, cls).setup_credentials()

    @classmethod
    def setup_clients(cls):
        super(BaseTelemetryTest, cls).setup_clients()
        cls.telemetry_client = cls.os_primary.telemetry_client
        cls.servers_client = cls.os_primary.servers_client
        cls.flavors_client = cls.os_primary.flavors_client
        cls.image_client_v2 = cls.os_primary.image_client_v2

    @classmethod
    def resource_setup(cls):
        super(BaseTelemetryTest, cls).resource_setup()
        cls.nova_notifications = ['memory', 'vcpus', 'disk.root.size',
                                  'disk.ephemeral.size']

        cls.glance_v2_notifications = ['image.download', 'image.serve']

        cls.server_ids = []
        cls.image_ids = []

    @classmethod
    def create_server(cls):
        tenant_network = cls.get_tenant_network()
        body, server = compute.create_test_server(
            cls.os_primary,
            tenant_network=tenant_network,
            name=data_utils.rand_name('ceilometer-instance'),
            wait_until='ACTIVE')
        cls.server_ids.append(body['id'])
        return body

    @classmethod
    def create_image(cls, client, **kwargs):
        body = client.create_image(name=data_utils.rand_name('image'),
                                   container_format='bare',
                                   disk_format='raw',
                                   **kwargs)
        # TODO(jswarren) Move ['image'] up to initial body value assignment
        # once both v1 and v2 glance clients include the full response
        # object.
        if 'image' in body:
            body = body['image']
        cls.image_ids.append(body['id'])
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
        cls.cleanup_resources(cls.servers_client.delete_server, cls.server_ids)
        cls.cleanup_resources(cls.image_client_v2.delete_image, cls.image_ids)
        super(BaseTelemetryTest, cls).resource_cleanup()

    def await_samples(self, metric, query):
        """This method is to wait for sample to add it to database.

        There are long time delays when using Postgresql (or Mysql)
        database as ceilometer backend
        """
        timeout = CONF.compute.build_timeout
        start = timeutils.utcnow()
        while timeutils.delta_seconds(start, timeutils.utcnow()) < timeout:
            body = self.telemetry_client.list_samples(metric, query)
            if body:
                return body
            time.sleep(CONF.compute.build_interval)

        raise lib_exc.TimeoutException(
            'Sample for metric:%s with query:%s has not been added to the '
            'database within %d seconds' % (metric, query,
                                            CONF.compute.build_timeout))


class BaseTelemetryAdminTest(BaseTelemetryTest):
    """Base test case class for admin Telemetry API tests."""

    credentials = ['primary', 'admin']

    @classmethod
    def setup_clients(cls):
        super(BaseTelemetryAdminTest, cls).setup_clients()
        cls.telemetry_admin_client = cls.os_adm.telemetry_client
