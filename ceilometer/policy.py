# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 OpenStack, LLC.
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

"""Policy Engine For Ceilometer."""

import os

from oslo.config import cfg

from ceilometer.openstack.common import policy
from ceilometer import utils


OPTS = [
    cfg.StrOpt('policy_file',
               default='policy.json',
               help='JSON file representing policy'),
    cfg.StrOpt('policy_default_rule',
               default='default',
               help='Rule checked when requested rule is not found'),
]

cfg.CONF.register_opts(OPTS)

_POLICY_PATH = None
_POLICY_CACHE = {}


def init():
    global _POLICY_PATH
    global _POLICY_CACHE
    if not _POLICY_PATH:
        _POLICY_PATH = cfg.CONF.policy_file
        if not os.path.exists(_POLICY_PATH):
            _POLICY_PATH = cfg.CONF.find_file(_POLICY_PATH)
        if not _POLICY_PATH:
            raise cfg.ConfigFilesNotFoundError([cfg.CONF.policy_file])
    utils.read_cached_file(_POLICY_PATH, _POLICY_CACHE,
                           reload_func=_set_rules)


def _set_rules(data):
    default_rule = cfg.CONF.policy_default_rule
    policy.set_rules(policy.Rules.load_json(data, default_rule))


def check_is_admin(roles):
    """Whether or not roles contains 'admin' role according to policy setting.

    """
    init()

    return policy.check('context_is_admin', {}, {'roles': roles})
