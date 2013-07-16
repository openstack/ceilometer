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
"""Publish a counter using the preferred RPC mechanism.
"""

import hashlib
import hmac
import itertools
import operator
import uuid
import urlparse

from oslo.config import cfg

from ceilometer.openstack.common import log
from ceilometer.openstack.common import rpc
from ceilometer import publisher
from ceilometer import utils


LOG = log.getLogger(__name__)

METER_PUBLISH_OPTS = [
    cfg.StrOpt('metering_topic',
               default='metering',
               help='the topic ceilometer uses for metering messages',
               deprecated_group="DEFAULT",
               ),
    cfg.StrOpt('metering_secret',
               secret=True,
               default='change this or be hacked',
               help='Secret value for signing metering messages',
               deprecated_group="DEFAULT",
               ),
]


def register_opts(config):
    """Register the options for publishing metering messages.
    """
    config.register_opts(METER_PUBLISH_OPTS, group="publisher_rpc")


register_opts(cfg.CONF)


def compute_signature(message, secret):
    """Return the signature for a message dictionary.
    """
    digest_maker = hmac.new(secret, '', hashlib.sha256)
    for name, value in utils.recursive_keypairs(message):
        if name == 'message_signature':
            # Skip any existing signature value, which would not have
            # been part of the original message.
            continue
        digest_maker.update(name)
        digest_maker.update(unicode(value).encode('utf-8'))
    return digest_maker.hexdigest()


def verify_signature(message, secret):
    """Check the signature in the message against the value computed
    from the rest of the contents.
    """
    old_sig = message.get('message_signature')
    new_sig = compute_signature(message, secret)
    return new_sig == old_sig


def meter_message_from_counter(counter, secret, source):
    """Make a metering message ready to be published or stored.

    Returns a dictionary containing a metering message
    for a notification message and a Counter instance.
    """
    msg = {'source': source,
           'counter_name': counter.name,
           'counter_type': counter.type,
           'counter_unit': counter.unit,
           'counter_volume': counter.volume,
           'user_id': counter.user_id,
           'project_id': counter.project_id,
           'resource_id': counter.resource_id,
           'timestamp': counter.timestamp,
           'resource_metadata': counter.resource_metadata,
           'message_id': str(uuid.uuid1()),
           }
    msg['message_signature'] = compute_signature(msg, secret)
    return msg


class RPCPublisher(publisher.PublisherBase):

    def __init__(self, parsed_url):
        options = urlparse.parse_qs(parsed_url.query)
        self.per_meter_topic = bool(int(
            options.get('per_meter_topic', [0])[-1]))
        self.target = options.get('target', ['record_metering_data'])[0]

    def publish_counters(self, context, counters, source):
        """Publish counters on RPC.

        :param context: Execution context from the service or RPC call.
        :param counters: Counters from pipeline after transformation.
        :param source: Counter source.

        """

        meters = [
            meter_message_from_counter(
                counter,
                cfg.CONF.publisher_rpc.metering_secret,
                source)
            for counter in counters
        ]

        topic = cfg.CONF.publisher_rpc.metering_topic
        msg = {
            'method': self.target,
            'version': '1.0',
            'args': {'data': meters},
        }
        LOG.audit('Publishing %d counters on %s',
                  len(msg['args']['data']), topic)
        rpc.cast(context, topic, msg)

        if self.per_meter_topic:
            for meter_name, meter_list in itertools.groupby(
                    sorted(meters, key=operator.itemgetter('counter_name')),
                    operator.itemgetter('counter_name')):
                msg = {
                    'method': self.target,
                    'version': '1.0',
                    'args': {'data': list(meter_list)},
                }
                topic_name = topic + '.' + meter_name
                LOG.audit('Publishing %d counters on %s',
                          len(msg['args']['data']), topic_name)
                rpc.cast(context, topic_name, msg)
