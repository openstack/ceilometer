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


def decode_unicode(input):
    """Decode the unicode of the message, and encode it into utf-8."""
    if isinstance(input, dict):
        temp = {}
        # If the input data is a dict, create an equivalent dict with a
        # predictable insertion order to avoid inconsistencies in the
        # message signature computation for equivalent payloads modulo
        # ordering
        for key, value in sorted(input.items()):
            temp[decode_unicode(key)] = decode_unicode(value)
        return temp
    elif isinstance(input, (tuple, list)):
        # When doing a pair of JSON encode/decode operations to the tuple,
        # the tuple would become list. So we have to generate the value as
        # list here.
        return [decode_unicode(element) for element in input]
    elif isinstance(input, str):
        return input.encode('utf-8')
    elif isinstance(input, bytes):
        return input.decode('utf-8')
    else:
        return input


def recursive_keypairs(d, separator=':'):
    """Generator that produces sequence of keypairs for nested dictionaries."""
    for name, value in sorted(d.items()):
        if isinstance(value, dict):
            for subname, subvalue in recursive_keypairs(value, separator):
                yield ('{}{}{}'.format(name, separator, subname), subvalue)
        elif isinstance(value, (tuple, list)):
            yield name, decode_unicode(value)
        else:
            yield name, value


def compute_signature(message, secret):
    """Return the signature for a message dictionary."""
    if not secret:
        return ''

    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    digest_maker = hmac.new(secret, b'', hashlib.sha256)
    for name, value in recursive_keypairs(message):
        if name == 'message_signature':
            # Skip any existing signature value, which would not have
            # been part of the original message.
            continue
        digest_maker.update(str(name).encode('utf-8'))
        digest_maker.update(str(value).encode('utf-8'))
    return digest_maker.hexdigest()


def verify_signature(message, secret):
    """Check the signature in the message.

    Message is verified against the value computed from the rest of the
    contents.
    """
    if not secret:
        return True

    old_sig = message.get('message_signature', '')
    new_sig = compute_signature(message, secret)

    if isinstance(old_sig, str):
        try:
            old_sig = old_sig.encode('ascii')
        except UnicodeDecodeError:
            return False
    new_sig = new_sig.encode('ascii')

    return hmac.compare_digest(new_sig, old_sig)


def meter_message_from_counter(sample, secret, publisher_id=None):
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
           'user_name': sample.user_name,
           'project_id': sample.project_id,
           'project_name': sample.project_name,
           'resource_id': sample.resource_id,
           'timestamp': sample.timestamp,
           'resource_metadata': sample.resource_metadata,
           'message_id': sample.id,
           'monotonic_time': sample.monotonic_time,
           }
    if publisher_id is not None:
        msg['publisher_id'] = publisher_id
    msg['message_signature'] = compute_signature(msg, secret)
    return msg


def message_from_event(event, secret):
    """Make an event message ready to be published or stored.

    Returns a serialized model of Event containing an event message
    """
    msg = event.serialize()
    msg['message_signature'] = compute_signature(msg, secret)
    return msg
