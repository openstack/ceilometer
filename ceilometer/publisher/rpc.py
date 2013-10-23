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
"""Publish a sample using the preferred RPC mechanism.
"""

import hashlib
import hmac
import itertools
import operator
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

cfg.CONF.import_opt('rabbit_max_retries',
                    'ceilometer.openstack.common.rpc.impl_kombu')


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


def meter_message_from_counter(sample, secret):
    """Make a metering message ready to be published or stored.

    Returns a dictionary containing a metering message
    for a notification message and a Sample instance.
    """
    msg = {'source': sample.source,
           'counter_name': sample.name,
           'counter_type': sample.type,
           'counter_unit': sample.unit,
           'counter_volume': sample.volume,
           'user_id': sample.user_id,
           'project_id': sample.project_id,
           'resource_id': sample.resource_id,
           'timestamp': sample.timestamp,
           'resource_metadata': sample.resource_metadata,
           'message_id': sample.id,
           }
    msg['message_signature'] = compute_signature(msg, secret)
    return msg


class RPCPublisher(publisher.PublisherBase):

    def __init__(self, parsed_url):
        options = urlparse.parse_qs(parsed_url.query)
        # the values of the option is a list of url params values
        # only take care of the latest one if the option
        # is provided more than once
        self.per_meter_topic = bool(int(
            options.get('per_meter_topic', [0])[-1]))

        self.target = options.get('target', ['record_metering_data'])[0]

        self.policy = options.get('policy', ['default'])[-1]
        self.max_queue_length = int(options.get(
            'max_queue_length', [1024])[-1])

        self.local_queue = []

        if self.policy in ['queue', 'drop']:
            LOG.info('Publishing policy set to %s, \
                     override rabbit_max_retries to 1' % self.policy)
            cfg.CONF.set_override("rabbit_max_retries", 1)

        elif self.policy == 'default':
            LOG.info('Publishing policy set to %s' % self.policy)
        else:
            LOG.warn('Publishing policy is unknown (%s) force to default'
                     % self.policy)
            self.policy = 'default'

    def publish_samples(self, context, samples):
        """Publish samples on RPC.

        :param context: Execution context from the service or RPC call.
        :param samples: Samples from pipeline after transformation.

        """

        meters = [
            meter_message_from_counter(
                sample,
                cfg.CONF.publisher_rpc.metering_secret)
            for sample in samples
        ]

        topic = cfg.CONF.publisher_rpc.metering_topic
        msg = {
            'method': self.target,
            'version': '1.0',
            'args': {'data': meters},
        }
        LOG.audit('Publishing %d samples on %s',
                  len(msg['args']['data']), topic)
        self.local_queue.append((context, topic, msg))

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
                LOG.audit('Publishing %d samples on %s',
                          len(msg['args']['data']), topic_name)
                self.local_queue.append((context, topic_name, msg))

        self.flush()

    def flush(self):
        #note(sileht):
        # IO of the rpc stuff in handled by eventlet,
        # this is why the self.local_queue, is emptied before processing the
        # queue and the remaining messages in the queue are added to
        # self.local_queue after in case of a other call have already added
        # something in the self.local_queue
        queue = self.local_queue
        self.local_queue = []
        self.local_queue = self._process_queue(queue, self.policy) + \
            self.local_queue
        if self.policy == 'queue':
            self._check_queue_length()

    def _check_queue_length(self):
        queue_length = len(self.local_queue)
        if queue_length > self.max_queue_length > 0:
            count = queue_length - self.max_queue_length
            self.local_queue = self.local_queue[count:]
            LOG.warn("Publisher max local_queue length is exceeded, "
                     "dropping %d oldest samples", count)

    @staticmethod
    def _process_queue(queue, policy):
        #note(sileht):
        # the behavior of rpc.cast call depends of rabbit_max_retries
        # if rabbit_max_retries <= 0:
        #   it returns only if the msg has been sent on the amqp queue
        # if rabbit_max_retries > 0:
        #   it raises a exception if rabbitmq is unreachable
        #
        # Ugly, but actually the oslo.rpc do a sys.exit(1) instead of a
        # RPCException, so we catch both until a correct behavior is
        # implemented in oslo
        #
        # the default policy just respect the rabbitmq configuration
        # nothing special is done if rabbit_max_retries <= 0
        # and exception is reraised if rabbit_max_retries > 0
        while queue:
            context, topic, msg = queue[0]
            try:
                rpc.cast(context, topic, msg)
            except (SystemExit, rpc.common.RPCException):
                samples = sum([len(m['args']['data']) for _, _, m in queue])
                if policy == 'queue':
                    LOG.warn("Failed to publish %s samples, queue them",
                             samples)
                    return queue
                elif policy == 'drop':
                    LOG.warn("Failed to publish %d samples, dropping them",
                             samples)
                    return []
                # default, occur only if rabbit_max_retries > 0
                raise
            else:
                queue.pop(0)
        return []
