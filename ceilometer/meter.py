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

import hmac
import hashlib
import uuid


# FIXME(dhellmann): Need to move this secret out of the code. Where?
SECRET = 'secrete'


def compute_signature(message):
    """Return the signature for a message dictionary.
    """
    digest_maker = hmac.new(SECRET, '', hashlib.sha256)
    for name, value in sorted(message.iteritems()):
        if name == 'message_signature':
            # Skip any existing signature value, which would not have
            # been part of the original message.
            continue
        digest_maker.update(name)
        digest_maker.update(unicode(value).encode('utf-8'))
    return digest_maker.hexdigest()


def meter_message_from_counter(notice, counter):
    """Make a metering message ready to be published or stored.

    Returns a dictionary containing a metering message
    for a notification message and a Counter instance.
    """
    msg = {'source': counter.source,
           'counter_type': counter.type,
           'counter_volume': counter.volume,
           'user_id': notice['payload']['user_id'],
           'project_id': notice['payload']['tenant_id'],
           'resource_id': counter.resource_id,
           'counter_datetime': counter.datetime,
           'counter_duration': counter.duration,
           'resource_metadata': counter.resource_metadata,
           'message_id': str(uuid.uuid1()),
           }
    msg['message_signature'] = compute_signature(msg)
    return msg
