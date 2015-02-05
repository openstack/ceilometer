#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 IBM Corp.
# Copyright 2013 eNovance <licensing@enovance.com>
# Copyright Ericsson AB 2013. All rights reserved
# Copyright 2014 Hewlett-Packard Company
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

from ceilometer.api.controllers.v2 import alarms
from ceilometer.api.controllers.v2 import capabilities
from ceilometer.api.controllers.v2 import events
from ceilometer.api.controllers.v2 import meters
from ceilometer.api.controllers.v2 import query
from ceilometer.api.controllers.v2 import resources
from ceilometer.api.controllers.v2 import samples


class V2Controller(object):
    """Version 2 API controller root."""

    resources = resources.ResourcesController()
    meters = meters.MetersController()
    samples = samples.SamplesController()
    alarms = alarms.AlarmsController()
    event_types = events.EventTypesController()
    events = events.EventsController()
    query = query.QueryController()
    capabilities = capabilities.CapabilitiesController()
