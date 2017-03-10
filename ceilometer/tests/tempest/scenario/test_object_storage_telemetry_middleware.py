# Copyright 2014 Red Hat
#
# All Rights Reserved.
#
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

from oslo_log import log as logging
from tempest import config
from tempest.lib.common.utils import data_utils
from tempest.lib.common.utils import test_utils
from tempest.lib import decorators
from tempest import test

from ceilometer.tests.tempest.service import client


CONF = config.CONF

LOG = logging.getLogger(__name__)


class ClientManager(client.Manager):

    load_clients = [
        'telemetry_client',
        'container_client',
        'object_client',
    ]


class TestObjectStorageTelemetry(test.BaseTestCase):
    """Test that swift uses the ceilometer middleware.

     * create container.
     * upload a file to the created container.
     * retrieve the file from the created container.
     * wait for notifications from ceilometer.
    """

    credentials = ['primary']
    client_manager = ClientManager

    @classmethod
    def skip_checks(cls):
        super(TestObjectStorageTelemetry, cls).skip_checks()
        if ("gnocchi" in CONF.service_available and
                CONF.service_available.gnocchi):
            skip_msg = ("%s skipped as gnocchi is enabled" %
                        cls.__name__)
            raise cls.skipException(skip_msg)
        if not CONF.service_available.swift:
            skip_msg = ("%s skipped as swift is not available" %
                        cls.__name__)
            raise cls.skipException(skip_msg)
        if not CONF.service_available.ceilometer:
            skip_msg = ("%s skipped as ceilometer is not available" %
                        cls.__name__)
            raise cls.skipException(skip_msg)

    @classmethod
    def setup_credentials(cls):
        cls.set_network_resources()
        super(TestObjectStorageTelemetry, cls).setup_credentials()

    @classmethod
    def setup_clients(cls):
        super(TestObjectStorageTelemetry, cls).setup_clients()
        cls.telemetry_client = cls.os_primary.telemetry_client
        cls.container_client = cls.os_primary.container_client
        cls.object_client = cls.os_primary.object_client

    def _confirm_notifications(self, container_name, obj_name):
        # NOTE: Loop seeking for appropriate notifications about the containers
        # and objects sent to swift.

        def _check_samples():
            # NOTE: Return True only if we have notifications about some
            # containers and some objects and the notifications are about
            # the expected containers and objects.
            # Otherwise returning False will case _check_samples to be
            # called again.
            results = self.telemetry_client.list_samples(
                'storage.objects.incoming.bytes')
            LOG.debug('got samples %s', results)

            # Extract container info from samples.
            containers, objects = [], []
            for sample in results:
                meta = sample['resource_metadata']
                if meta.get('container') and meta['container'] != 'None':
                    containers.append(meta['container'])
                elif (meta.get('target.metadata:container') and
                      meta['target.metadata:container'] != 'None'):
                    containers.append(meta['target.metadata:container'])

                if meta.get('object') and meta['object'] != 'None':
                    objects.append(meta['object'])
                elif (meta.get('target.metadata:object') and
                      meta['target.metadata:object'] != 'None'):
                    objects.append(meta['target.metadata:object'])

            return (container_name in containers and obj_name in objects)

        self.assertTrue(
            test_utils.call_until_true(_check_samples,
                                       CONF.telemetry.notification_wait,
                                       CONF.telemetry.notification_sleep),
            'Correct notifications were not received after '
            '%s seconds.' % CONF.telemetry.notification_wait)

    def create_container(self):
        name = data_utils.rand_name('swift-scenario-container')
        self.container_client.create_container(name)
        # look for the container to assure it is created
        self.container_client.list_container_contents(name)
        LOG.debug('Container %s created' % (name))
        self.addCleanup(self.container_client.delete_container,
                        name)
        return name

    def upload_object_to_container(self, container_name):
        obj_name = data_utils.rand_name('swift-scenario-object')
        obj_data = data_utils.arbitrary_string()
        self.object_client.create_object(container_name, obj_name, obj_data)
        self.addCleanup(self.object_client.delete_object,
                        container_name,
                        obj_name)
        return obj_name

    @decorators.idempotent_id('6d6b88e5-3e38-41bc-b34a-79f713a6cb85')
    @test.services('object_storage')
    def test_swift_middleware_notifies(self):
        container_name = self.create_container()
        obj_name = self.upload_object_to_container(container_name)
        self._confirm_notifications(container_name, obj_name)
