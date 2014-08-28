#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

import abc
import itertools
import operator

from oslo.config import cfg
import oslo.messaging
import oslo.messaging._drivers.common
import six
import six.moves.urllib.parse as urlparse

from ceilometer import messaging
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer import publisher
from ceilometer.publisher import utils


LOG = log.getLogger(__name__)

METER_PUBLISH_RPC_OPTS = [
    cfg.StrOpt('metering_topic',
               default='metering',
               help='The topic that ceilometer uses for metering messages.',
               deprecated_group="DEFAULT",
               ),
]

METER_PUBLISH_NOTIFIER_OPTS = [
    cfg.StrOpt('metering_topic',
               default='metering',
               help='The topic that ceilometer uses for metering '
               'notifications.',
               ),
    cfg.StrOpt('metering_driver',
               default='messagingv2',
               help='The driver that ceilometer uses for metering '
               'notifications.',
               )
]

cfg.CONF.register_opts(METER_PUBLISH_RPC_OPTS,
                       group="publisher_rpc")
cfg.CONF.register_opts(METER_PUBLISH_NOTIFIER_OPTS,
                       group="publisher_notifier")
cfg.CONF.import_opt('host', 'ceilometer.service')


def oslo_messaging_is_rabbit():
    kombu = ['ceilometer.openstack.common.rpc.impl_kombu',
             'oslo.messaging._drivers.impl_rabbit:RabbitDriver'
             'rabbit']
    return cfg.CONF.rpc_backend in kombu or (
        cfg.CONF.transport_url and
        cfg.CONF.transport_url.startswith('rabbit://'))


def override_backend_retry_config(value):
    """Override the retry config option native to the configured rpc backend.

    It is done if such a native config option exists.
    :param value: the value to override
    """
    # TODO(sileht): ultimately we should add to olso a more generic concept
    # of retry config (i.e. not specific to an individual AMQP provider)
    # see: https://bugs.launchpad.net/ceilometer/+bug/1244698
    # and: https://bugs.launchpad.net/oslo.messaging/+bug/1282639
    if oslo_messaging_is_rabbit():
        if 'rabbit_max_retries' in cfg.CONF:
            cfg.CONF.set_override('rabbit_max_retries', value)


@six.add_metaclass(abc.ABCMeta)
class MessagingPublisher(publisher.PublisherBase):

    def __init__(self, parsed_url):
        options = urlparse.parse_qs(parsed_url.query)
        # the values of the option is a list of url params values
        # only take care of the latest one if the option
        # is provided more than once
        self.per_meter_topic = bool(int(
            options.get('per_meter_topic', [0])[-1]))

        self.policy = options.get('policy', ['default'])[-1]
        self.max_queue_length = int(options.get(
            'max_queue_length', [1024])[-1])

        self.local_queue = []

        if self.policy in ['queue', 'drop']:
            LOG.info(_('Publishing policy set to %s, '
                       'override backend retry config to 1') % self.policy)
            override_backend_retry_config(1)
        elif self.policy == 'default':
            LOG.info(_('Publishing policy set to %s') % self.policy)
        else:
            LOG.warn(_('Publishing policy is unknown (%s) force to default')
                     % self.policy)
            self.policy = 'default'

    def publish_samples(self, context, samples):
        """Publish samples on RPC.

        :param context: Execution context from the service or RPC call.
        :param samples: Samples from pipeline after transformation.

        """

        meters = [
            utils.meter_message_from_counter(
                sample,
                cfg.CONF.publisher.metering_secret)
            for sample in samples
        ]

        topic = cfg.CONF.publisher_rpc.metering_topic
        self.local_queue.append((context, topic, meters))

        if self.per_meter_topic:
            for meter_name, meter_list in itertools.groupby(
                    sorted(meters, key=operator.itemgetter('counter_name')),
                    operator.itemgetter('counter_name')):
                meter_list = list(meter_list)
                topic_name = topic + '.' + meter_name
                LOG.debug('Publishing %(m)d samples on %(n)s',
                          {'m': len(meter_list), 'n': topic_name})
                self.local_queue.append((context, topic_name, meter_list))

        self.flush()

    def flush(self):
        # NOTE(sileht):
        # IO of the rpc stuff in handled by eventlet,
        # this is why the self.local_queue, is emptied before processing the
        # queue and the remaining messages in the queue are added to
        # self.local_queue after in case of a other call have already added
        # something in the self.local_queue
        queue = self.local_queue
        self.local_queue = []
        self.local_queue = (self._process_queue(queue, self.policy) +
                            self.local_queue)
        if self.policy == 'queue':
            self._check_queue_length()

    def _check_queue_length(self):
        queue_length = len(self.local_queue)
        if queue_length > self.max_queue_length > 0:
            count = queue_length - self.max_queue_length
            self.local_queue = self.local_queue[count:]
            LOG.warn(_("Publisher max local_queue length is exceeded, "
                     "dropping %d oldest samples") % count)

    def _process_queue(self, queue, policy):
        # NOTE(sileht):
        # the behavior of rpc.cast call depends of rabbit_max_retries
        # if rabbit_max_retries <= 0:
        #   it returns only if the msg has been sent on the amqp queue
        # if rabbit_max_retries > 0:
        #   it raises an exception if rabbitmq is unreachable
        #
        # the default policy just respect the rabbitmq configuration
        # nothing special is done if rabbit_max_retries <= 0
        # and exception is reraised if rabbit_max_retries > 0
        while queue:
            context, topic, meters = queue[0]
            try:
                self._send(context, topic, meters)
            except oslo.messaging._drivers.common.RPCException:
                samples = sum([len(m) for __, __, m in queue])
                if policy == 'queue':
                    LOG.warn(_("Failed to publish %d samples, queue them"),
                             samples)
                    return queue
                elif policy == 'drop':
                    LOG.warn(_("Failed to publish %d samples, dropping them"),
                             samples)
                    return []
                # default, occur only if rabbit_max_retries > 0
                raise
            else:
                queue.pop(0)
        return []

    @abc.abstractmethod
    def _send(self, context, topic, meters):
        """Send the meters to the messaging topic."""


class RPCPublisher(MessagingPublisher):
    def __init__(self, parsed_url):
        super(RPCPublisher, self).__init__(parsed_url)

        options = urlparse.parse_qs(parsed_url.query)
        self.target = options.get('target', ['record_metering_data'])[0]

        self.rpc_client = messaging.get_rpc_client(
            messaging.get_transport(),
            version='1.0'
        )

    def _send(self, context, topic, meters):
        self.rpc_client.prepare(topic=topic).cast(context, self.target,
                                                  data=meters)


class NotifierPublisher(MessagingPublisher):
    def __init__(self, parsed_url):
        super(NotifierPublisher, self).__init__(parsed_url)
        self.notifier = oslo.messaging.Notifier(
            messaging.get_transport(),
            driver=cfg.CONF.publisher_notifier.metering_driver,
            publisher_id='metering.publisher.%s' % cfg.CONF.host,
            topic=cfg.CONF.publisher_notifier.metering_topic
        )

    def _send(self, context, event_type, meters):
        self.notifier.sample(context.to_dict(), event_type=event_type,
                             payload=meters)
