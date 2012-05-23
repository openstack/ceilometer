# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Counter class for holding data about a metering event.

A Counter doesn't really do anything, but we need a way to
ensure that all of the appropriate fields have been filled
in by the plugins that create them.
"""

import collections


Counter = collections.namedtuple('Counter',
                                 ' '.join(['source',
                                           'type',
                                           'volume',
                                           'user_id',
                                           'project_id',
                                           'resource_id',
                                           'datetime',
                                           'duration',
                                           'resource_metadata',
                                           ])
                                 )
