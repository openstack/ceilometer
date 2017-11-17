# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Justin Santa Barbara

# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Utilities and helper functions."""

import calendar
import datetime
import decimal
import threading
import time

from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_utils import units
import six

ROOTWRAP_CONF = "/etc/ceilometer/rootwrap.conf"

OPTS = [
    cfg.StrOpt('rootwrap_config',
               default=ROOTWRAP_CONF,
               help='Path to the rootwrap configuration file to '
                    'use for running commands as root'),
]


def _get_root_helper():
    global ROOTWRAP_CONF
    return 'sudo ceilometer-rootwrap %s' % ROOTWRAP_CONF


def setup_root_helper(conf):
    global ROOTWRAP_CONF
    ROOTWRAP_CONF = conf.rootwrap_config


def execute(*cmd, **kwargs):
    """Convenience wrapper around oslo's execute() method."""
    if 'run_as_root' in kwargs and 'root_helper' not in kwargs:
        kwargs['root_helper'] = _get_root_helper()
    return processutils.execute(*cmd, **kwargs)


def decode_unicode(input):
    """Decode the unicode of the message, and encode it into utf-8."""
    if isinstance(input, dict):
        temp = {}
        # If the input data is a dict, create an equivalent dict with a
        # predictable insertion order to avoid inconsistencies in the
        # message signature computation for equivalent payloads modulo
        # ordering
        for key, value in sorted(six.iteritems(input)):
            temp[decode_unicode(key)] = decode_unicode(value)
        return temp
    elif isinstance(input, (tuple, list)):
        # When doing a pair of JSON encode/decode operations to the tuple,
        # the tuple would become list. So we have to generate the value as
        # list here.
        return [decode_unicode(element) for element in input]
    elif isinstance(input, six.text_type):
        return input.encode('utf-8')
    elif six.PY3 and isinstance(input, six.binary_type):
        return input.decode('utf-8')
    else:
        return input


def recursive_keypairs(d, separator=':'):
    """Generator that produces sequence of keypairs for nested dictionaries."""
    for name, value in sorted(six.iteritems(d)):
        if isinstance(value, dict):
            for subname, subvalue in recursive_keypairs(value, separator):
                yield ('%s%s%s' % (name, separator, subname), subvalue)
        elif isinstance(value, (tuple, list)):
            yield name, decode_unicode(value)
        else:
            yield name, value


def dt_to_decimal(utc):
    """Datetime to Decimal.

    Some databases don't store microseconds in datetime
    so we always store as Decimal unixtime.
    """
    if utc is None:
        return None

    decimal.getcontext().prec = 30
    return (decimal.Decimal(str(calendar.timegm(utc.utctimetuple()))) +
            (decimal.Decimal(str(utc.microsecond)) /
            decimal.Decimal("1000000.0")))


def decimal_to_dt(dec):
    """Return a datetime from Decimal unixtime format."""
    if dec is None:
        return None

    integer = int(dec)
    micro = (dec - decimal.Decimal(integer)) * decimal.Decimal(units.M)
    daittyme = datetime.datetime.utcfromtimestamp(integer)
    return daittyme.replace(microsecond=int(round(micro)))


def hash_of_set(s):
    return str(hash(frozenset(s)))


def kill_listeners(listeners):
    # NOTE(gordc): correct usage of oslo.messaging listener is to stop(),
    # which stops new messages, and wait(), which processes remaining
    # messages and closes connection
    for listener in listeners:
        listener.stop()
        listener.wait()


def delayed(delay, target, *args, **kwargs):
    time.sleep(delay)
    return target(*args, **kwargs)


def spawn_thread(target, *args, **kwargs):
    t = threading.Thread(target=target, args=args, kwargs=kwargs)
    t.daemon = True
    t.start()
    return t
