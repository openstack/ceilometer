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
"""Test API against SQLAlchemy.
"""
from . import list_events
from . import list_meters
from . import list_users


class TestListEvents(list_events.TestListEvents):
    database_connection = 'sqlite://'


class TestListEmptyMeters(list_meters.TestListEmptyMeters):
    database_connection = 'sqlite://'


class TestListMeters(list_meters.TestListMeters):
    database_connection = 'sqlite://'


class TestListEmptyUsers(list_users.TestListEmptyUsers):
    database_connection = 'sqlite://'


class TestListUsers(list_users.TestListUsers):
    database_connection = 'sqlite://'
