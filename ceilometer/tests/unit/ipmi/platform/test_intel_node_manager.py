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

import abc
import tempfile

import mock
from oslotest import base
import six

from ceilometer.ipmi.platform import intel_node_manager as node_manager
from ceilometer import service
from ceilometer.tests.unit.ipmi.platform import fake_utils
from ceilometer import utils


@six.add_metaclass(abc.ABCMeta)
class _Base(base.BaseTestCase):

    @abc.abstractmethod
    def init_test_engine(self):
        """Prepare specific ipmitool as engine for different NM version."""

    def setUp(self):
        super(_Base, self).setUp()
        conf = service.prepare_service([], [])
        self.init_test_engine()
        with mock.patch.object(node_manager.NodeManager, '__new__',
                               side_effect=self._new_no_singleton):
            self.nm = node_manager.NodeManager(conf)

    @staticmethod
    def _new_no_singleton(cls, *args, **kwargs):
        if six.PY3:
            # We call init manually due to a py3 bug:
            # https://bugs.python.org/issue25731
            obj = super(node_manager.NodeManager, cls).__new__(cls)
            obj.__init__(*args, **kwargs)
            return obj
        else:
            return super(node_manager.NodeManager, cls).__new__(
                cls, *args, **kwargs)


class TestNodeManagerV3(_Base):

    def init_test_engine(self):
        utils.execute = mock.Mock(side_effect=fake_utils.execute_with_nm_v3)

    def test_read_airflow(self):
        airflow = self.nm.read_airflow()
        avg_val = node_manager._hex(airflow["Average_value"])
        max_val = node_manager._hex(airflow["Maximum_value"])
        min_val = node_manager._hex(airflow["Minimum_value"])
        cur_val = node_manager._hex(airflow["Current_value"])

        # get NM 3.0
        self.assertEqual(5, self.nm.nm_version)

        # see ipmi_test_data.py for raw data
        self.assertEqual(190, cur_val)
        self.assertEqual(150, min_val)
        self.assertEqual(550, max_val)
        self.assertEqual(203, avg_val)

    def test_read_outlet_temperature(self):
        temperature = self.nm.read_outlet_temperature()
        avg_val = node_manager._hex(temperature["Average_value"])
        max_val = node_manager._hex(temperature["Maximum_value"])
        min_val = node_manager._hex(temperature["Minimum_value"])
        cur_val = node_manager._hex(temperature["Current_value"])

        # get NM 3.0
        self.assertEqual(5, self.nm.nm_version)

        # see ipmi_test_data.py for raw data
        self.assertEqual(25, cur_val)
        self.assertEqual(24, min_val)
        self.assertEqual(27, max_val)
        self.assertEqual(25, avg_val)

    def test_read_cups_utilization(self):
        cups_util = self.nm.read_cups_utilization()
        cpu_util = node_manager._hex(cups_util["CPU_Utilization"])
        mem_util = node_manager._hex(cups_util["Mem_Utilization"])
        io_util = node_manager._hex(cups_util["IO_Utilization"])

        # see ipmi_test_data.py for raw data
        self.assertEqual(51, cpu_util)
        self.assertEqual(5, mem_util)
        self.assertEqual(0, io_util)

    def test_read_cups_index(self):
        cups_index = self.nm.read_cups_index()
        index = node_manager._hex(cups_index["CUPS_Index"])
        self.assertEqual(46, index)


class TestNodeManager(_Base):

    def init_test_engine(self):
        utils.execute = mock.Mock(side_effect=fake_utils.execute_with_nm_v2)

    def test_read_power_all(self):
        power = self.nm.read_power_all()

        avg_val = node_manager._hex(power["Average_value"])
        max_val = node_manager._hex(power["Maximum_value"])
        min_val = node_manager._hex(power["Minimum_value"])
        cur_val = node_manager._hex(power["Current_value"])

        # get NM 2.0
        self.assertEqual(3, self.nm.nm_version)
        # see ipmi_test_data.py for raw data
        self.assertEqual(87, cur_val)
        self.assertEqual(3, min_val)
        self.assertEqual(567, max_val)
        self.assertEqual(92, avg_val)

    def test_read_inlet_temperature(self):
        temperature = self.nm.read_inlet_temperature()

        avg_val = node_manager._hex(temperature["Average_value"])
        max_val = node_manager._hex(temperature["Maximum_value"])
        min_val = node_manager._hex(temperature["Minimum_value"])
        cur_val = node_manager._hex(temperature["Current_value"])

        # see ipmi_test_data.py for raw data
        self.assertEqual(23, cur_val)
        self.assertEqual(22, min_val)
        self.assertEqual(24, max_val)
        self.assertEqual(23, avg_val)

    def test_read_airflow(self):
        airflow = self.nm.read_airflow()
        self.assertEqual({}, airflow)

    def test_read_outlet_temperature(self):
        temperature = self.nm.read_outlet_temperature()
        self.assertEqual({}, temperature)

    def test_read_cups_utilization(self):
        cups_util = self.nm.read_cups_utilization()
        self.assertEqual({}, cups_util)

    def test_read_cups_index(self):
        cups_index = self.nm.read_cups_index()
        self.assertEqual({}, cups_index)


class TestNonNodeManager(_Base):

    def init_test_engine(self):
        utils.execute = mock.Mock(side_effect=fake_utils.execute_without_nm)

    def test_read_power_all(self):
        # no NM support
        self.assertEqual(0, self.nm.nm_version)
        power = self.nm.read_power_all()

        # Non-Node Manager platform return empty data
        self.assertEqual({}, power)

    def test_read_inlet_temperature(self):
        temperature = self.nm.read_inlet_temperature()

        # Non-Node Manager platform return empty data
        self.assertEqual({}, temperature)


class ParseSDRFileTestCase(base.BaseTestCase):

    def setUp(self):
        super(ParseSDRFileTestCase, self).setUp()
        self.temp_file = tempfile.NamedTemporaryFile().name

    def test_parsing_found(self):
        data = b'\x00\xFF\x00\xFF\x57\x01\x00\x0D\x01\x0A\xB2\x00\xFF'
        with open(self.temp_file, 'wb') as f:
            f.write(data)
        result = node_manager.NodeManager._parse_slave_and_channel(
            self.temp_file)
        self.assertEqual(('0a', 'b'), result)

    def test_parsing_not_found(self):
        data = b'\x00\xFF\x00\xFF\x52\x01\x80\x0D\x01\x6A\xB7\x00\xFF'
        with open(self.temp_file, 'wb') as f:
            f.write(data)
        result = node_manager.NodeManager._parse_slave_and_channel(
            self.temp_file)
        self.assertIsNone(result)
