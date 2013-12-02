#
# Copyright 2014 NEC Corporation.  All rights reserved.
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


from ceilometer.network import statistics
from ceilometer import sample


class FlowPollster(statistics._Base):

    meter_name = 'switch.flow'
    meter_type = sample.TYPE_GAUGE
    meter_unit = 'flow'


class FlowPollsterDurationSeconds(statistics._Base):

    meter_name = 'switch.flow.duration_seconds'
    meter_type = sample.TYPE_GAUGE
    meter_unit = 's'


class FlowPollsterDurationNanoseconds(statistics._Base):

    meter_name = 'switch.flow.duration_nanoseconds'
    meter_type = sample.TYPE_GAUGE
    meter_unit = 'ns'


class FlowPollsterPackets(statistics._Base):

    meter_name = 'switch.flow.packets'
    meter_type = sample.TYPE_CUMULATIVE
    meter_unit = 'packet'


class FlowPollsterBytes(statistics._Base):

    meter_name = 'switch.flow.bytes'
    meter_type = sample.TYPE_CUMULATIVE
    meter_unit = 'B'
