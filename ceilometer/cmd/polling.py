# -*- encoding: utf-8 -*-
#
# Copyright 2014-2015 OpenStack Foundation
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
from oslo_log import log
from oslo_service import service as os_service

from ceilometer.agent import manager
from ceilometer.i18n import _LW
from ceilometer import service

LOG = log.getLogger(__name__)

CONF = cfg.CONF


class MultiChoicesOpt(cfg.Opt):
    def __init__(self, name, choices=None, **kwargs):
        super(MultiChoicesOpt, self).__init__(
            name, type=DeduplicatedCfgList(choices), **kwargs)
        self.choices = choices

    def _get_argparse_kwargs(self, group, **kwargs):
        """Extends the base argparse keyword dict for multi choices options."""
        kwargs = super(MultiChoicesOpt, self)._get_argparse_kwargs(group)
        kwargs['nargs'] = '+'
        choices = kwargs.get('choices', self.choices)
        if choices:
            kwargs['choices'] = choices
        return kwargs


class DeduplicatedCfgList(cfg.types.List):
    def __init__(self, choices=None, **kwargs):
        super(DeduplicatedCfgList, self).__init__(**kwargs)
        self.choices = choices or []

    def __call__(self, *args, **kwargs):
        result = super(DeduplicatedCfgList, self).__call__(*args, **kwargs)
        result_set = set(result)
        if len(result) != len(result_set):
            LOG.warning(_LW("Duplicated values: %s found in CLI options, "
                            "auto de-duplicated"), result)
            result = list(result_set)
        if self.choices and not (result_set <= set(self.choices)):
            raise Exception('Valid values are %s, but found %s'
                            % (self.choices, result))
        return result


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
    os_service.launch(CONF, manager.AgentManager(CONF.polling_namespaces,
                                                 CONF.pollster_list)).wait()
