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

import cotyledon
from cotyledon import oslo_config_glue
from oslo_config import cfg
from oslo_log import log

from ceilometer.agent import manager
from ceilometer import service

LOG = log.getLogger(__name__)


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
            LOG.warning("Duplicated values: %s found in CLI options, "
                        "auto de-duplicated", result)
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
                    deprecated_for_removal=True,
                    dest='pollster_list',
                    help='List of pollsters (or wildcard templates) to be '
                         'used while polling. This option is deprecated. '
                         'Configure pollsters via polling.yaml'),
]


def create_polling_service(worker_id, conf):
    return manager.AgentManager(worker_id,
                                conf,
                                conf.polling_namespaces,
                                conf.pollster_list)


def main():
    conf = cfg.ConfigOpts()
    conf.register_cli_opts(CLI_OPTS)
    service.prepare_service(conf=conf)
    sm = cotyledon.ServiceManager()
    sm.add(create_polling_service, args=(conf,))
    oslo_config_glue.setup(sm, conf)
    sm.run()
