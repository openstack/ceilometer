# -*- encoding: utf-8 -*-
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

# from . import acl
# from . import alarm
# from . import compute_duration_by_resource
# from . import list_events
from . import list_meters
# from . import list_resources
from . import post_samples
# from . import statistics


# TODO(jd) Fix the HBase driver to pass these tests!
# class TestAPIAcl(acl.TestAPIACL):
#     database_connection = 'hbase://__test__'

# TODO(jd) Fix the HBase driver to pass these tests!
# class TestListEvents(list_events.TestListEvents):
#     database_connection = 'hbase://__test__'

# TODO(jd) Fix the HBase driver to pass these tests!
# class TestListEmptyAlarms(alarm.TestListEmptyAlarms):
#     database_connection = 'hbase://__test__'

# TODO(jd) Fix the HBase driver to pass these tests!
# class TestAlarms(alarm.TestAlarms):
#     database_connection = 'hbase://__test__'

# TODO(jd) Fix the HBase driver to pass these tests!
# class TestComputeDurationByResource(
#         compute_duration_by_resource.TestComputeDurationByResource):
#     database_connection = 'hbase://__test__'


class TestListEmptyMeters(list_meters.TestListEmptyMeters):
    database_connection = 'hbase://__test__'

# TODO(jd) Fix the HBase driver to pass these tests!
# class TestListMeters(list_meters.TestListMeters):
#     database_connection = 'hbase://__test__'

# TODO(jd) Fix the HBase driver to pass these tests!
# class TestListResources(list_resources.TestListResources):
#     database_connection = 'hbase://__test__'

# TODO(jd) Fix the HBase driver to pass these tests!
# class TestMaxProjectVolume(statistics.TestMaxProjectVolume):
#     database_connection = 'hbase://__test__'

# TODO(jd) Fix the HBase driver to pass these tests!
# class TestMaxResourceVolume(statistics.TestMaxResourceVolume):
#     database_connection = 'hbase://__test__'

# TODO(jd) Fix the HBase driver to pass these tests!
# class TestSumProjectVolume(statistics.TestSumProjectVolume):
#     database_connection = 'hbase://__test__'

# TODO(jd) Fix the HBase driver to pass these tests!
# class TestSumResourceVolume(statistics.TestSumProjectVolume):
#     database_connection = 'hbase://__test__'


class TestPostSamples(post_samples.TestPostSamples):
    database_connection = 'hbase://__test__'
