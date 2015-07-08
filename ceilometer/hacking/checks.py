# Copyright 2015 Huawei Technologies Co., Ltd.
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

"""
Guidelines for writing new hacking checks

 - Use only for Ceilometer specific tests. OpenStack general tests
   should be submitted to the common 'hacking' module.
 - Pick numbers in the range C3xx. Find the current test with
   the highest allocated number and then pick the next value.
 - Keep the test method code in the source file ordered based
   on the C3xx value.
 - List the new rule in the top level HACKING.rst file
 - Add test cases for each new rule to ceilometer/tests/test_hacking.py

"""

import re


# TODO(zqfan): When other oslo libraries switch over non-namespace'd
# imports, we need to add them to the regexp below.
oslo_namespace_imports = re.compile(
    r"(from|import) oslo[.](concurrency|config|utils|i18n|serialization)")


def check_oslo_namespace_imports(logical_line, physical_line, filename):
    if re.match(oslo_namespace_imports, logical_line):
        msg = ("C300: '%s' must be used instead of '%s'." % (
               logical_line.replace('oslo.', 'oslo_'),
               logical_line))
        yield(0, msg)


def factory(register):
    register(check_oslo_namespace_imports)
