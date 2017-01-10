#
# Copyright 2015 Red Hat. All Rights Reserved.
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

"""A test module to exercise the Gnocchi API with gabbi."""

import os

from gabbi import driver


TESTS_DIR = 'gabbits-live'


def load_tests(loader, tests, pattern):
    """Provide a TestSuite to the discovery process."""
    NEEDED_ENV = ["AODH_SERVICE_URL", "GNOCCHI_SERVICE_URL",
                  "HEAT_SERVICE_URL", "NOVA_SERVICE_URL", "PANKO_SERVICE_URL",
                  "GLANCE_IMAGE_NAME", "ADMIN_TOKEN"]

    for env_variable in NEEDED_ENV:
        if not os.getenv(env_variable):
            if os.getenv("GABBI_LIVE_FAIL_IF_NO_TEST"):
                raise RuntimeError('%s is not set' % env_variable)
            else:
                return

    test_dir = os.path.join(os.path.dirname(__file__), TESTS_DIR)
    return driver.build_tests(test_dir, loader, host="localhost", port=8041)
