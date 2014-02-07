# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
#         Tyaptin Ilya <ityaptin@mirantis.com>
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
"""Utils for publishers
"""

import hashlib
import hmac

from oslo.config import cfg

from ceilometer import utils

METER_PUBLISH_OPTS = [
    cfg.StrOpt('metering_secret',
               secret=True,
               default='change this or be hacked',
               help='Secret value for signing metering messages.',
               deprecated_opts=[cfg.DeprecatedOpt("metering_secret",
                                                  "DEFAULT"),
                                cfg.DeprecatedOpt("metering_secret",
                                                  "publisher_rpc")]
               ),
]


def register_opts(config):
    """Register the options for publishing metering messages.
    """
    config.register_opts(METER_PUBLISH_OPTS, group="publisher")


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
