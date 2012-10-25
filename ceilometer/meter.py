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
"""Compute the signature of a metering message.
"""

import hashlib
import hmac
import uuid

from ceilometer.openstack.common import cfg

METER_OPTS = [
    cfg.StrOpt('metering_secret',
               default='change this or be hacked',
               help='Secret value for signing metering messages',
               ),
    cfg.StrOpt('counter_source',
               default='openstack',
               help='Source for counters emited on this instance',
               ),
    ]


def register_opts(config):
    """Register the options for signing metering messages.
    """
    config.register_opts(METER_OPTS)


register_opts(cfg.CONF)


def recursive_keypairs(d):
    """Generator that produces sequence of keypairs for nested dictionaries.
    """
    for name, value in sorted(d.iteritems()):
        if isinstance(value, dict):
            for subname, subvalue in recursive_keypairs(value):
                yield ('%s:%s' % (name, subname), subvalue)
        else:
            yield name, value


def compute_signature(message, secret):
    """Return the signature for a message dictionary.
    """
    digest_maker = hmac.new(secret, '', hashlib.sha256)
    for name, value in recursive_keypairs(message):
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
