# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance
#
# Author: Julien Danjou <julien@danjou.info>
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
"""Test API against MongoDB.
"""
from . import list_events
from . import list_meters


class TestListEvents(list_events.TestListEvents):
    database_connection = 'test://'


class TestListEventsMetaQuery(list_events.TestListEventsMetaquery):
    database_connection = 'test://'


class TestListEmptyMeters(list_meters.TestListEmptyMeters):
    database_connection = 'test://'


class TestListMeters(list_meters.TestListMeters):
    database_connection = 'test://'


class TestListMetersMetaquery(list_meters.TestListMetersMetaquery):
    database_connection = 'test://'
