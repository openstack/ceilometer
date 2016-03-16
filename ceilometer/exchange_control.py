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

from oslo_config import cfg

EXCHANGE_OPTS = [
    cfg.StrOpt('heat_control_exchange',
               default='heat',
               help="Exchange name for Heat notifications"),
    cfg.StrOpt('glance_control_exchange',
               default='glance',
               help="Exchange name for Glance notifications."),
    cfg.StrOpt('magnetodb_control_exchange',
               default='magnetodb',
               help="Exchange name for Magnetodb notifications."),
    cfg.StrOpt('keystone_control_exchange',
               default='keystone',
               help="Exchange name for Keystone notifications."),
    cfg.StrOpt('cinder_control_exchange',
               default='cinder',
               help="Exchange name for Cinder notifications."),
    cfg.StrOpt('sahara_control_exchange',
               default='sahara',
               help="Exchange name for Data Processing notifications."),
    cfg.StrOpt('swift_control_exchange',
               default='swift',
               help="Exchange name for Swift notifications."),
    cfg.StrOpt('magnum_control_exchange',
               default='magnum',
               help="Exchange name for Magnum notifications."),
    cfg.StrOpt('trove_control_exchange',
               default='trove',
               help="Exchange name for DBaaS notifications."),
    cfg.StrOpt('zaqar_control_exchange',
               default='zaqar',
               help="Exchange name for Messaging service notifications."),
    cfg.StrOpt('dns_control_exchange',
               default='central',
               help="Exchange name for DNS service notifications."),
]
