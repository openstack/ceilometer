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

from gabbi import runner
from gabbi import suitemaker
from gabbi import utils
from tempest import config
from tempest.scenario import manager

TEST_DIR = os.path.join(os.path.dirname(__file__), '..', '..',
                        'integration', 'gabbi', 'gabbits-live')


class TestTelemetryIntegration(manager.ScenarioTest):
    credentials = ['admin', 'primary']

    TIMEOUT_SCALING_FACTOR = 5

    @classmethod
    def skip_checks(cls):
        super(TestTelemetryIntegration, cls).skip_checks()
        for name in ["aodh_plugin", "gnocchi", "nova", "heat_plugin", "panko",
                     "ceilometer", "glance"]:
            cls._check_service(name)

    @classmethod
    def _check_service(cls, name):
        if not getattr(config.CONF.service_available, name, False):
            raise cls.skipException("%s support is required" %
                                    name.capitalize())

    @staticmethod
    def _get_endpoint(auth, service):
        opt_section = getattr(config.CONF, service)
        endpoint_type = opt_section.endpoint_type
        is_keystone_v3 = 'catalog' in auth[1]

        if is_keystone_v3:
            if endpoint_type.endswith("URL"):
                endpoint_type = endpoint_type[:-3]
            catalog = auth[1]['catalog']
            endpoints = [e['endpoints'] for e in catalog
                         if e['type'] == opt_section.catalog_type]
            if not endpoints:
                raise Exception("%s endpoint not found" %
                                opt_section.catalog_type)
            endpoints = [e['url'] for e in endpoints[0]
                         if e['interface'] == endpoint_type]
            if not endpoints:
                raise Exception("%s interface not found for endpoint %s" %
                                (endpoint_type,
                                 opt_section.catalog_type))
            return endpoints[0]

        else:
            if not endpoint_type.endswith("URL"):
                endpoint_type += "URL"
            catalog = auth[1]['serviceCatalog']
            endpoints = [e for e in catalog
                         if e['type'] == opt_section.catalog_type]
            if not endpoints:
                raise Exception("%s endpoint not found" %
                                opt_section.catalog_type)
            return endpoints[0]['endpoints'][0][endpoint_type]

    def _do_test(self, filename):
        admin_auth = self.os_admin.auth_provider.get_auth()
        auth = self.os_primary.auth_provider.get_auth()
        networks = self.os_primary.networks_client.list_networks(
            **{'router:external': False, 'fields': 'id'})['networks']

        os.environ.update({
            "ADMIN_TOKEN": admin_auth[0],
            "USER_TOKEN": auth[0],
            "AODH_GRANULARITY": str(config.CONF.telemetry.alarm_granularity),
            "AODH_SERVICE_URL": self._get_endpoint(auth, "alarming_plugin"),
            "GNOCCHI_SERVICE_URL": self._get_endpoint(auth, "metric"),
            "PANKO_SERVICE_URL": self._get_endpoint(auth, "event"),
            "HEAT_SERVICE_URL": self._get_endpoint(auth, "heat_plugin"),
            "NOVA_SERVICE_URL": self._get_endpoint(auth, "compute"),
            "GLANCE_SERVICE_URL": self._get_endpoint(auth, "image"),
            "GLANCE_IMAGE_NAME": self.glance_image_create(),
            "NOVA_FLAVOR_REF": config.CONF.compute.flavor_ref,
            "NEUTRON_NETWORK": networks[0].get('id'),
        })

        with open(os.path.join(TEST_DIR, filename)) as f:
            test_suite = suitemaker.test_suite_from_dict(
                loader=unittest.defaultTestLoader,
                test_base_name="gabbi",
                suite_dict=utils.load_yaml(f),
                test_directory=TEST_DIR,
                host=None, port=None,
                fixture_module=None,
                intercept=None,
                handlers=runner.initialize_handlers([]),
                test_loader_name="tempest")

            # NOTE(sileht): We hide stdout/stderr and reraise the failure
            # manually, tempest will print it itself.
            with open(os.devnull, 'w') as stream:
                result = unittest.TextTestRunner(
                    stream=stream, verbosity=0, failfast=True,
                ).run(test_suite)

            if not result.wasSuccessful():
                failures = (result.errors + result.failures +
                            result.unexpectedSuccesses)
                if failures:
                    test, bt = failures[0]
                    name = test.test_data.get('name', test.id())
                    msg = 'From test "%s" :\n%s' % (name, bt)
                    self.fail(msg)

            self.assertTrue(result.wasSuccessful())


def test_maker(name, filename):
    def test(self):
        self._do_test(filename)
        test.__name__ = name
    return test


# Create one scenario per yaml file
for filename in os.listdir(TEST_DIR):
    if not filename.endswith('.yaml'):
        continue
    name = "test_%s" % filename[:-5].lower().replace("-", "_")
    setattr(TestTelemetryIntegration, name,
            test_maker(name, filename))
