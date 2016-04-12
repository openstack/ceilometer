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

import os
import unittest

from gabbi import driver
from tempest import config
from tempest import test

from ceilometer.tests.tempest.service import client


class ClientManager(client.Manager):
    load_clients = [
        'image_client_v2',
    ]


class TestAutoscalingGabbi(test.BaseTestCase):
    credentials = ['admin']
    client_manager = ClientManager

    @classmethod
    def skip_checks(cls):
        super(TestAutoscalingGabbi, cls).skip_checks()
        for name in ["aodh_plugin", "gnocchi", "nova", "heat",
                     "ceilometer", "glance"]:
            cls._check_service(name)

    @classmethod
    def _check_service(cls, name):
        if not getattr(config.CONF.service_available, name, False):
            raise cls.skipException("%s support is required" %
                                    name.capitalize())

    @classmethod
    def resource_setup(cls):
        super(TestAutoscalingGabbi, cls).resource_setup()
        test_dir = os.path.join(os.path.dirname(__file__), '..', '..',
                                'integration', 'gabbi', 'gabbits-live')
        cls.tests = driver.build_tests(
            test_dir, unittest.TestLoader(),
            host='localhost', port='13245',
            test_loader_name='tempest.scenario.telemetry-autoscaling.test')

        auth = cls.os_admin.auth_provider.get_auth()
        os.environ["ADMIN_TOKEN"] = auth[0]
        os.environ["AODH_SERVICE_URL"] = cls._get_endpoint_for(
            auth, "alarming_plugin")
        os.environ["GNOCCHI_SERVICE_URL"] = cls._get_endpoint_for(
            auth, "metric")
        os.environ["HEAT_SERVICE_URL"] = cls._get_endpoint_for(
            auth, "orchestration")
        os.environ["NOVA_SERVICE_URL"] = cls._get_endpoint_for(auth, "compute")
        os.environ["GLANCE_SERVICE_URL"] = cls._get_endpoint_for(auth, "image")
        images = cls.os_admin.image_client_v2.list_images()["images"]
        for img in images:
            name = img["name"]
            if name.startswith("cirros") and name.endswith("-uec"):
                os.environ["GLANCE_IMAGE_NAME"] = name
                break
        else:
            cls.skipException("A cirros-.*-uec image is required")

    @staticmethod
    def clear_credentials():
        # FIXME(sileht): We don't want the token to be invalided, but
        # for some obcurs reason, clear_credentials is called before/during run
        # So, make the one used by tearDropClass a dump, and call it manually
        # in run()
        pass

    def run(self, result=None):
        self.setUp()
        try:
            self.tests.run(result)
        finally:
            super(TestAutoscalingGabbi, self).clear_credentials()
            self.tearDown()

    @staticmethod
    def _get_endpoint_for(auth, service):
        opt_section = getattr(config.CONF, service)
        endpoint_type = opt_section.endpoint_type
        if not endpoint_type.endswith("URL"):
            endpoint_type += "URL"

        endpoints = [e for e in auth[1]['serviceCatalog']
                     if e['type'] == opt_section.catalog_type]
        if not endpoints:
            raise Exception("%s endpoint not found" %
                            config.CONF.metric.catalog_type)
        return endpoints[0]['endpoints'][0][endpoint_type]

    @staticmethod
    def test_fake():
        # NOTE(sileht): A fake test is needed to have the class loaded
        # by the test runner
        pass
