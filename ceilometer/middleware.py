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

from oslo.config import cfg

from ceilometer import plugin
from ceilometer import sample

cfg.CONF.import_opt('nova_control_exchange',
                    'ceilometer.compute.notifications')
cfg.CONF.import_opt('glance_control_exchange',
                    'ceilometer.image.notifications')
cfg.CONF.import_opt('neutron_control_exchange',
                    'ceilometer.network.notifications')
cfg.CONF.import_opt('cinder_control_exchange',
                    'ceilometer.volume.notifications')

OPTS = [
    cfg.MultiStrOpt('http_control_exchanges',
                    default=[cfg.CONF.nova_control_exchange,
                             cfg.CONF.glance_control_exchange,
                             cfg.CONF.neutron_control_exchange,
                             cfg.CONF.cinder_control_exchange],
                    help="Exchanges name to listen for notifications."),
]

cfg.CONF.register_opts(OPTS)


class HTTPRequest(plugin.NotificationBase):
    event_types = ['http.request']

    @staticmethod
    def get_exchange_topics(conf):
        """Return a sequence of ExchangeTopics defining the exchange and
        topics to be connected for this plugin.
        """
        return [
            plugin.ExchangeTopics(
                exchange=exchange,
                topics=set(topic + ".info"
                           for topic in conf.notification_topics))
            for exchange in conf.http_control_exchanges
        ]

    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name=message['event_type'],
            type=sample.TYPE_DELTA,
            volume=1,
            unit=message['event_type'].split('.')[1],
            user_id=message['payload']['request'].get('HTTP_X_USER_ID'),
            project_id=message['payload']['request'].get('HTTP_X_PROJECT_ID'),
            resource_id=message['payload']['request'].get(
                'HTTP_X_SERVICE_NAME'),
            message=message)


class HTTPResponse(HTTPRequest):
    event_types = ['http.response']
