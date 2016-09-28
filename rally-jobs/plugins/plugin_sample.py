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

"""Sample of plugin for Ceilometer.

For more Ceilometer related benchmarks take a look here:
github.com/openstack/rally/blob/master/rally/benchmark/scenarios/ceilometer/

About plugins: https://rally.readthedocs.org/en/latest/plugins.html

Rally concepts https://wiki.openstack.org/wiki/Rally/Concepts
"""

from rally.benchmark.scenarios import base


class CeilometerPlugin(base.Scenario):
    pass
