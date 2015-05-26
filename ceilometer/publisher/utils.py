#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

from oslo_config import cfg
import six

from ceilometer import utils

OPTS = [
    cfg.StrOpt('telemetry_secret',
               secret=True,
               default='change this for valid signing',
               help='Secret value for signing messages. Set value empty if '
                    'signing is not required to avoid computational overhead.',
               deprecated_opts=[cfg.DeprecatedOpt("metering_secret",
                                                  "DEFAULT"),
                                cfg.DeprecatedOpt("metering_secret",
                                                  "publisher_rpc"),
                                cfg.DeprecatedOpt("metering_secret",
                                                  "publisher")]
               ),
]
cfg.CONF.register_opts(OPTS, group="publisher")


def compute_signature(message, secret):
    """Return the signature for a message dictionary."""
    if not secret:
        return ''

    if isinstance(secret, six.text_type):
        secret = secret.encode('utf-8')
    digest_maker = hmac.new(secret, b'', hashlib.sha256)
    for name, value in utils.recursive_keypairs(message):
        if name == 'message_signature':
            # Skip any existing signature value, which would not have
            # been part of the original message.
            continue
        digest_maker.update(six.text_type(name).encode('utf-8'))
        digest_maker.update(six.text_type(value).encode('utf-8'))
    return digest_maker.hexdigest()


def besteffort_compare_digest(first, second):
    """Returns True if both string inputs are equal, otherwise False.

    This function should take a constant amount of time regardless of
    how many characters in the strings match.

    """
    # NOTE(sileht): compare_digest method protected for timing-attacks
    # exists since python >= 2.7.7 and python >= 3.3
    # this a bit less-secure python fallback version
    # taken from https://github.com/openstack/python-keystoneclient/blob/
    # master/keystoneclient/middleware/memcache_crypt.py#L88
    if len(first) != len(second):
        return False
    result = 0
    if six.PY3 and isinstance(first, bytes) and isinstance(second, bytes):
        for x, y in zip(first, second):
            result |= x ^ y
    else:
        for x, y in zip(first, second):
            result |= ord(x) ^ ord(y)
    return result == 0


if hasattr(hmac, 'compare_digest'):
    compare_digest = hmac.compare_digest
else:
    compare_digest = besteffort_compare_digest


def verify_signature(message, secret):
    """Check the signature in the message.

    Message is verified against the value computed from the rest of the
    contents.
    """
    if not secret:
        return True

    old_sig = message.get('message_signature', '')
    new_sig = compute_signature(message, secret)

    if isinstance(old_sig, six.text_type):
        try:
            old_sig = old_sig.encode('ascii')
        except UnicodeDecodeError:
            return False
    if six.PY3:
        new_sig = new_sig.encode('ascii')

    return compare_digest(new_sig, old_sig)


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


def message_from_event(event, secret):
    """Make an event message ready to be published or stored.

    Returns a serialized model of Event containing an event message
    """
    msg = event.serialize()
    msg['message_signature'] = compute_signature(msg, secret)
    return msg
