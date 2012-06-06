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
"""Storage backend management
"""

import pkg_resources

from ceilometer import cfg
from ceilometer import log

LOG = log.getLogger(__name__)

STORAGE_ENGINE_NAMESPACE = 'ceilometer.storage'

STORAGE_OPTS = [
    cfg.StrOpt('metering_storage_engine',
               default='log',
               help='The name of the storage engine to use',
               ),
    ]


def register_opts(conf):
    """Register any options for the storage system.
    """
    conf.register_opts(STORAGE_OPTS)
    p = get_engine(conf)
    p.register_opts(conf)


def get_engine(conf):
    """Load the configured engine and return an instance.
    """
    engine_name = conf.metering_storage_engine
    for ep in pkg_resources.iter_entry_points(STORAGE_ENGINE_NAMESPACE,
                                              engine_name):
        try:
            engine_class = ep.load()
            engine = engine_class()
        except Exception as err:
            LOG.error('Failed to load storage engine %s: %s',
                      engine_name, err)
            LOG.exception(err)
            raise
        LOG.info('Loaded %s storage engine', engine_name)
        return engine
    else:
        raise RuntimeError('No %r storage engine found' % engine_name)
