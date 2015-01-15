# -*- encoding: utf-8 -*-
#
# Copyright 2014 OpenStack Foundation
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

from oslo_config import cfg

from ceilometer.agent import manager
from ceilometer.openstack.common import service as os_service
from ceilometer import service

CONF = cfg.CONF


class MultiChoicesOpt(cfg.Opt):
    def __init__(self, name, choices=None, **kwargs):
        super(MultiChoicesOpt, self).__init__(name,
                                              type=cfg.types.List(),
                                              **kwargs)
        self.choices = choices

    def _get_argparse_kwargs(self, group, **kwargs):
        """Extends the base argparse keyword dict for multi choices options."""
        kwargs = super(MultiChoicesOpt, self)._get_argparse_kwargs(group)
        kwargs['nargs'] = '+'
        choices = kwargs.get('choices', self.choices)
        if choices:
            kwargs['choices'] = choices
        return kwargs

CLI_OPTS = [
    MultiChoicesOpt('polling-namespaces',
                    default=['compute', 'central'],
                    choices=['compute', 'central', 'ipmi'],
                    dest='polling_namespaces',
                    help='Polling namespace(s) to be used while '
                         'resource polling'),
    MultiChoicesOpt('pollster-list',
                    default=[],
                    dest='pollster_list',
                    help='List of pollsters (or wildcard templates) to be '
                         'used while polling'),
]

CONF.register_cli_opts(CLI_OPTS)


def main():
    service.prepare_service()
    os_service.launch(manager.AgentManager(CONF.polling_namespaces,
                                           CONF.pollster_list)).wait()


# todo(dbelova): remove it someday. Needed for backward compatibility
def main_compute():
    service.prepare_service()
    os_service.launch(manager.AgentManager(['compute'])).wait()


# todo(dbelova): remove it someday. Needed for backward compatibility
def main_central():
    service.prepare_service()
    os_service.launch(manager.AgentManager(['central'])).wait()


def main_ipmi():
    service.prepare_service()
    os_service.launch(manager.AgentManager(['ipmi'])).wait()
