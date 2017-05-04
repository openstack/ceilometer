# Copyright 2012 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_config import cfg


service_option = cfg.BoolOpt('ceilometer',
                             default=True,
                             help="Whether or not Ceilometer is expected to be"
                                  "available")

telemetry_group = cfg.OptGroup(name='telemetry',
                               title='Telemetry Service Options')

TelemetryGroup = [
    cfg.StrOpt('catalog_type',
               default='metering',
               help="Catalog type of the Telemetry service."),
    cfg.StrOpt('endpoint_type',
               default='publicURL',
               choices=['public', 'admin', 'internal',
                        'publicURL', 'adminURL', 'internalURL'],
               help="The endpoint type to use for the telemetry service."),
    cfg.BoolOpt('event_enabled',
                default=True,
                help="Runs Ceilometer event-related tests"),
    cfg.BoolOpt('deprecated_api_enabled',
                default=True,
                help="Runs Ceilometer deprecated API tests"),
    cfg.IntOpt('notification_wait',
               default=120,
               help="The seconds to wait for notifications which "
                    "containers and objects sent to swift."),
    cfg.IntOpt('notification_sleep',
               default=1,
               help="The seconds to sleep after an unsuccessful "
                    "notification received."),
    cfg.IntOpt('alarm_granularity',
               default=300,
               help="Granularity to use for aodh alarms. This must match the "
                    "configured Gnocchi archive policy")

]
