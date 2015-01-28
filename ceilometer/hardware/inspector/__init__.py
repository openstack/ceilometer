#
# Copyright 2014 Intel Corp.
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

from stevedore import driver


def get_inspector(parsed_url, namespace='ceilometer.hardware.inspectors'):
    """Get inspector driver and load it.

    :param parsed_url: urlparse.SplitResult object for the inspector
    :param namespace: Namespace to use to look for drivers.
    """
    loaded_driver = driver.DriverManager(namespace, parsed_url.scheme)
    return loaded_driver.driver()
