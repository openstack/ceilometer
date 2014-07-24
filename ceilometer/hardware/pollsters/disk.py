#
# Copyright 2013 ZHAW SoE
# Copyright 2014 Intel Corp.
#
# Authors: Lucas Graf <graflu0@students.zhaw.ch>
#          Toni Zehnder <zehndton@students.zhaw.ch>
#          Lianhao Lu <lianhao.lu@intel.com>
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

from ceilometer.hardware import plugin
from ceilometer.hardware.pollsters import util
from ceilometer import sample


class _Base(plugin.HardwarePollster):

    CACHE_KEY = 'disk'

    def generate_one_sample(self, host, c_data):
        value, metadata, extra = c_data
        res_id = host.hostname
        if metadata.get('device'):
            res_id = res_id + ".%s" % metadata.get('device')
        return util.make_sample_from_host(host,
                                          name=self.IDENTIFIER,
                                          sample_type=sample.TYPE_GAUGE,
                                          unit='B',
                                          volume=value,
                                          res_metadata=metadata,
                                          extra=extra,
                                          resource_id=res_id)


class DiskTotalPollster(_Base):
    IDENTIFIER = 'disk.size.total'


class DiskUsedPollster(_Base):
    IDENTIFIER = 'disk.size.used'
