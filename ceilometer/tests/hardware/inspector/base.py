#
# Copyright 2014 Intel Corp
#
# Authors: Lianhao Lu <lianhao.lu@intel.com>
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

from ceilometer.hardware.inspector import base


class InspectorBaseTest(object):
    """Subclass must set self.inspector and self.host in
    self.setUp()
    """

    cpu = [base.CPUStats(cpu_1_min=0.1,
                         cpu_5_min=0.2,
                         cpu_15_min=0.3),
           ]

    network = [(base.Interface(name='eth0',
                               mac='112233445566',
                               ip='10.0.0.1',
                               speed=1250000 / 8),
                base.InterfaceStats(rx_bytes=1000,
                                    tx_bytes=2000,
                                    error=1)),
               ]
    diskspace = [(base.Disk(device='/dev/sda1', path='/'),
                  base.DiskStats(size=1000, used=500),
                  ),
                 (base.Disk(device='/dev/sda2', path='/home'),
                  base.DiskStats(size=2000, used=1000),
                  ),
                 ]
    memory = [base.MemoryStats(total=1000, used=500)]

    def test_inspect_cpu(self):
        self.assertEqual(list(self.inspector.inspect_cpu(self.host)),
                         self.cpu)

    def test_inspect_network(self):
        self.assertEqual(list(self.inspector.inspect_network(self.host)),
                         self.network)

    def test_inspect_disk(self):
        self.assertEqual(list(self.inspector.inspect_disk(self.host)),
                         self.diskspace)

    def test_inspect_memory(self):
        self.assertEqual(list(self.inspector.inspect_memory(self.host)),
                         self.memory)
