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
    cfg.StrOpt('nova_control_exchange',
               default='nova',
               help="Exchange name for Nova notifications.",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
    cfg.StrOpt('neutron_control_exchange',
               default='neutron',
               help="Exchange name for Neutron notifications.",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
    cfg.StrOpt('heat_control_exchange',
               default='heat',
               help="Exchange name for Heat notifications",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
    cfg.StrOpt('glance_control_exchange',
               default='glance',
               help="Exchange name for Glance notifications.",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
    cfg.StrOpt('keystone_control_exchange',
               default='keystone',
               help="Exchange name for Keystone notifications.",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
    cfg.StrOpt('cinder_control_exchange',
               default='cinder',
               help="Exchange name for Cinder notifications.",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
    cfg.StrOpt('sahara_control_exchange',
               default='sahara',
               help="Exchange name for Data Processing notifications.",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
    cfg.StrOpt('swift_control_exchange',
               default='swift',
               help="Exchange name for Swift notifications.",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
    cfg.StrOpt('magnum_control_exchange',
               default='magnum',
               help="Exchange name for Magnum notifications.",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
    cfg.StrOpt('trove_control_exchange',
               default='trove',
               help="Exchange name for DBaaS notifications.",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
    cfg.StrOpt('zaqar_control_exchange',
               default='zaqar',
               help="Exchange name for Messaging service notifications.",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
    cfg.StrOpt('dns_control_exchange',
               default='central',
               help="Exchange name for DNS service notifications.",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
    cfg.StrOpt('ceilometer_control_exchange',
               default='ceilometer',
               help="Exchange name for ceilometer notifications.",
               deprecated_for_removal=True,
               deprecated_reason="Use notification_control_exchanges instead"),
]
