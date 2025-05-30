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

"""Sample data for test_ipmi_sensor.

This data is provided as a sample of the data expected from the ipmitool
binary, which produce Node Manager/IPMI raw data
"""

sensor_temperature_data = """Sensor ID              : SSB Therm Trip (0xd)
 Entity ID             : 7.1 (System Board)
 Sensor Type (Discrete): Temperature
 Assertions Enabled    : Digital State
                         [State Asserted]
 Deassertions Enabled  : Digital State
                         [State Asserted]

Sensor ID              : BB P1 VR Temp (0x20)
 Entity ID             : 7.1 (System Board)
 Sensor Type (Analog)  : Temperature
 Sensor Reading        : 25 (+/- 0) degrees C
 Status                : ok
 Nominal Reading       : 58.000
 Normal Minimum        : 10.000
 Normal Maximum        : 105.000
 Upper critical        : 115.000
 Upper non-critical    : 110.000
 Lower critical        : 0.000
 Lower non-critical    : 5.000
 Positive Hysteresis   : 2.000
 Negative Hysteresis   : 2.000
 Minimum sensor range  : Unspecified
 Maximum sensor range  : Unspecified
 Event Message Control : Per-threshold
 Readable Thresholds   : lcr lnc unc ucr
 Settable Thresholds   : lcr lnc unc ucr
 Threshold Read Mask   : lcr lnc unc ucr
 Assertion Events      :
 Assertions Enabled    : lnc- lcr- unc+ ucr+
 Deassertions Enabled  : lnc- lcr- unc+ ucr+

Sensor ID              : Front Panel Temp (0x21)
 Entity ID             : 12.1 (Front Panel Board)
 Sensor Type (Analog)  : Temperature
 Sensor Reading        : 23 (+/- 0) degrees C
 Status                : ok
 Nominal Reading       : 28.000
 Normal Minimum        : 10.000
 Normal Maximum        : 45.000
 Upper critical        : 55.000
 Upper non-critical    : 50.000
 Lower critical        : 0.000
 Lower non-critical    : 5.000
 Positive Hysteresis   : 2.000
 Negative Hysteresis   : 2.000
 Minimum sensor range  : Unspecified
 Maximum sensor range  : Unspecified
 Event Message Control : Per-threshold
 Readable Thresholds   : lcr lnc unc ucr
 Settable Thresholds   : lcr lnc unc ucr
 Threshold Read Mask   : lcr lnc unc ucr
 Assertion Events      :
 Assertions Enabled    : lnc- lcr- unc+ ucr+
 Deassertions Enabled  : lnc- lcr- unc+ ucr+

Sensor ID              : SSB Temp (0x22)
 Entity ID             : 7.1 (System Board)
 Sensor Type (Analog)  : Temperature
 Sensor Reading        : 43 (+/- 0) degrees C
 Status                : ok
 Nominal Reading       : 52.000
 Normal Minimum        : 10.000
 Normal Maximum        : 93.000
 Upper critical        : 103.000
 Upper non-critical    : 98.000
 Lower critical        : 0.000
 Lower non-critical    : 5.000
 Positive Hysteresis   : 2.000
 Negative Hysteresis   : 2.000
 Minimum sensor range  : Unspecified
 Maximum sensor range  : Unspecified
 Event Message Control : Per-threshold
 Readable Thresholds   : lcr lnc unc ucr
 Settable Thresholds   : lcr lnc unc ucr
 Threshold Read Mask   : lcr lnc unc ucr
 Assertion Events      :
 Assertions Enabled    : lnc- lcr- unc+ ucr+
 Deassertions Enabled  : lnc- lcr- unc+ ucr+

"""

sensor_voltage_data = """Sensor ID              : VR Watchdog (0xb)
 Entity ID             : 7.1 (System Board)
 Sensor Type (Discrete): Voltage
 Assertions Enabled    : Digital State
                         [State Asserted]
 Deassertions Enabled  : Digital State
                         [State Asserted]

Sensor ID              : BB +12.0V (0xd0)
 Entity ID             : 7.1 (System Board)
 Sensor Type (Analog)  : Voltage
 Sensor Reading        : 11.831 (+/- 0) Volts
 Status                : ok
 Nominal Reading       : 11.935
 Normal Minimum        : 11.363
 Normal Maximum        : 12.559
 Upper critical        : 13.391
 Upper non-critical    : 13.027
 Lower critical        : 10.635
 Lower non-critical    : 10.947
 Positive Hysteresis   : 0.052
 Negative Hysteresis   : 0.052
 Minimum sensor range  : Unspecified
 Maximum sensor range  : Unspecified
 Event Message Control : Per-threshold
 Readable Thresholds   : lcr lnc unc ucr
 Settable Thresholds   : lcr lnc unc ucr
 Threshold Read Mask   : lcr lnc unc ucr
 Assertion Events      :
 Assertions Enabled    : lnc- lcr- unc+ ucr+
 Deassertions Enabled  : lnc- lcr- unc+ ucr+

Sensor ID              : BB +1.35 P1LV AB (0xe4)
 Entity ID             : 7.1 (System Board)
 Sensor Type (Analog)  : Voltage
 Sensor Reading        : Disabled
 Status                : Disabled
 Nominal Reading       : 1.342
 Normal Minimum        : 1.275
 Normal Maximum        : 1.409
 Upper critical        : 1.488
 Upper non-critical    : 1.445
 Lower critical        : 1.201
 Lower non-critical    : 1.244
 Positive Hysteresis   : 0.006
 Negative Hysteresis   : 0.006
 Minimum sensor range  : Unspecified
 Maximum sensor range  : Unspecified
 Event Message Control : Per-threshold
 Readable Thresholds   : lcr lnc unc ucr
 Settable Thresholds   : lcr lnc unc ucr
 Threshold Read Mask   : lcr lnc unc ucr
 Event Status          : Unavailable
 Assertions Enabled    : lnc- lcr- unc+ ucr+
 Deassertions Enabled  : lnc- lcr- unc+ ucr+

Sensor ID              : BB +5.0V (0xd1)
 Entity ID             : 7.1 (System Board)
 Sensor Type (Analog)  : Voltage
 Sensor Reading        : 4.959 (+/- 0) Volts
 Status                : ok
 Nominal Reading       : 4.981
 Normal Minimum        : 4.742
 Normal Maximum        : 5.241
 Upper critical        : 5.566
 Upper non-critical    : 5.415
 Lower critical        : 4.416
 Lower non-critical    : 4.546
 Positive Hysteresis   : 0.022
 Negative Hysteresis   : 0.022
 Minimum sensor range  : Unspecified
 Maximum sensor range  : Unspecified
 Event Message Control : Per-threshold
 Readable Thresholds   : lcr lnc unc ucr
 Settable Thresholds   : lcr lnc unc ucr
 Threshold Read Mask   : lcr lnc unc ucr
 Assertion Events      :
 Assertions Enabled    : lnc- lcr- unc+ ucr+
 Deassertions Enabled  : lnc- lcr- unc+ ucr+

"""

sensor_current_data = """Sensor ID              : PS1 Curr Out % (0x58)
 Entity ID             : 10.1 (Power Supply)
 Sensor Type (Analog)  : Current
 Sensor Reading        : 11 (+/- 0) unspecified
 Status                : ok
 Nominal Reading       : 50.000
 Normal Minimum        : 0.000
 Normal Maximum        : 100.000
 Upper critical        : 118.000
 Upper non-critical    : 100.000
 Positive Hysteresis   : Unspecified
 Negative Hysteresis   : Unspecified
 Minimum sensor range  : Unspecified
 Maximum sensor range  : Unspecified
 Event Message Control : Per-threshold
 Readable Thresholds   : unc ucr
 Settable Thresholds   : unc ucr
 Threshold Read Mask   : unc ucr
 Assertion Events      :
 Assertions Enabled    : unc+ ucr+
 Deassertions Enabled  : unc+ ucr+

Sensor ID              : PS2 Curr Out % (0x59)
 Entity ID             : 10.2 (Power Supply)
 Sensor Type (Analog)  : Current
 Sensor Reading        : 0 (+/- 0) unspecified
 Status                : ok
 Nominal Reading       : 50.000
 Normal Minimum        : 0.000
 Normal Maximum        : 100.000
 Upper critical        : 118.000
 Upper non-critical    : 100.000
 Positive Hysteresis   : Unspecified
 Negative Hysteresis   : Unspecified
 Minimum sensor range  : Unspecified
 Maximum sensor range  : Unspecified
 Event Message Control : Per-threshold
 Readable Thresholds   : unc ucr
 Settable Thresholds   : unc ucr
 Threshold Read Mask   : unc ucr
 Assertion Events      :
 Assertions Enabled    : unc+ ucr+
 Deassertions Enabled  : unc+ ucr+

Sensor ID              : Pwr Consumption (0x76)
 Entity ID             : 7.1 (System Board)
 Sensor Type (Threshold)  : Current (0x03)
 Sensor Reading        : 154 (+/- 0) Watts
 Status                : ok
 Nominal Reading       : 1034.000
 Normal Maximum        : 1056.000
 Upper critical        : 1914.000
 Upper non-critical    : 1738.000
 Positive Hysteresis   : Unspecified
 Negative Hysteresis   : Unspecified
 Minimum sensor range  : Unspecified
 Maximum sensor range  : 5588.000
 Event Message Control : Per-threshold
 Readable Thresholds   : unc ucr
 Settable Thresholds   : unc
 Assertion Events      :
 Assertions Enabled    : unc+ ucr+
 Deassertions Enabled  : unc+ ucr+

"""

sensor_fan_data = """Sensor ID              : System Fan 1 (0x30)
 Entity ID             : 29.1 (Fan Device)
 Sensor Type (Analog)  : Fan
 Sensor Reading        : 4704 (+/- 0) RPM
 Status                : ok
 Nominal Reading       : 7497.000
 Normal Minimum        : 2499.000
 Normal Maximum        : 12495.000
 Lower critical        : 1715.000
 Lower non-critical    : 1960.000
 Positive Hysteresis   : 49.000
 Negative Hysteresis   : 49.000
 Minimum sensor range  : Unspecified
 Maximum sensor range  : Unspecified
 Event Message Control : Per-threshold
 Readable Thresholds   : lcr lnc
 Settable Thresholds   : lcr lnc
 Threshold Read Mask   : lcr lnc
 Assertion Events      :
 Assertions Enabled    : lnc- lcr-
 Deassertions Enabled  : lnc- lcr-

Sensor ID              : System Fan 2 (0x32)
 Entity ID             : 29.2 (Fan Device)
 Sensor Type (Analog)  : Fan
 Sensor Reading        : 4704 (+/- 0) RPM
 Status                : ok
 Nominal Reading       : 7497.000
 Normal Minimum        : 2499.000
 Normal Maximum        : 12495.000
 Lower critical        : 1715.000
 Lower non-critical    : 1960.000
 Positive Hysteresis   : 49.000
 Negative Hysteresis   : 49.000
 Minimum sensor range  : Unspecified
 Maximum sensor range  : Unspecified
 Event Message Control : Per-threshold
 Readable Thresholds   : lcr lnc
 Settable Thresholds   : lcr lnc
 Threshold Read Mask   : lcr lnc
 Assertion Events      :
 Assertions Enabled    : lnc- lcr-
 Deassertions Enabled  : lnc- lcr-

Sensor ID              : System Fan 3 (0x34)
 Entity ID             : 29.3 (Fan Device)
 Sensor Type (Analog)  : Fan
 Sensor Reading        : 4704 (+/- 0) RPM
 Status                : ok
 Nominal Reading       : 7497.000
 Normal Minimum        : 2499.000
 Normal Maximum        : 12495.000
 Lower critical        : 1715.000
 Lower non-critical    : 1960.000
 Positive Hysteresis   : 49.000
 Negative Hysteresis   : 49.000
 Minimum sensor range  : Unspecified
 Maximum sensor range  : Unspecified
 Event Message Control : Per-threshold
 Readable Thresholds   : lcr lnc
 Settable Thresholds   : lcr lnc
 Threshold Read Mask   : lcr lnc
 Assertion Events      :
 Assertions Enabled    : lnc- lcr-
 Deassertions Enabled  : lnc- lcr-

Sensor ID              : System Fan 4 (0x36)
 Entity ID             : 29.4 (Fan Device)
 Sensor Type (Analog)  : Fan
 Sensor Reading        : 4606 (+/- 0) RPM
 Status                : ok
 Nominal Reading       : 7497.000
 Normal Minimum        : 2499.000
 Normal Maximum        : 12495.000
 Lower critical        : 1715.000
 Lower non-critical    : 1960.000
 Positive Hysteresis   : 49.000
 Negative Hysteresis   : 49.000
 Minimum sensor range  : Unspecified
 Maximum sensor range  : Unspecified
 Event Message Control : Per-threshold
 Readable Thresholds   : lcr lnc
 Settable Thresholds   : lcr lnc
 Threshold Read Mask   : lcr lnc
 Assertion Events      :
 Assertions Enabled    : lnc- lcr-
 Deassertions Enabled  : lnc- lcr-

"""


sensor_status_cmd = 'ipmitoolraw0x0a0x2c0x00'
init_sensor_cmd = 'ipmitoolraw0x0a0x2c0x01'
sdr_info_cmd = 'ipmitoolsdrinfo'

read_sensor_all_cmd = 'ipmitoolsdr-v'
read_sensor_temperature_cmd = 'ipmitoolsdr-vtypeTemperature'
read_sensor_voltage_cmd = 'ipmitoolsdr-vtypeVoltage'
read_sensor_current_cmd = 'ipmitoolsdr-vtypeCurrent'
read_sensor_fan_cmd = 'ipmitoolsdr-vtypeFan'

sdr_info = ('', '')

sensor_temperature = (sensor_temperature_data, '')
sensor_voltage = (sensor_voltage_data, '')
sensor_current = (sensor_current_data, '')
sensor_fan = (sensor_fan_data, '')
