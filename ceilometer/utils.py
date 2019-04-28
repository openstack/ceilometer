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

import threading

from oslo_config import cfg

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


def spawn_thread(target, *args, **kwargs):
    t = threading.Thread(target=target, args=args, kwargs=kwargs)
    t.daemon = True
    t.start()
    return t
