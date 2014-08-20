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

import logging

from oslo.config import cfg

from ceilometer import service
from ceilometer import storage

cfg.CONF.import_opt('time_to_live', 'ceilometer.storage',
                    group='database')

LOG = logging.getLogger(__name__)


def dbsync():
    service.prepare_service()
    storage.get_connection_from_config(cfg.CONF).upgrade()
    storage.get_connection_from_config(cfg.CONF, 'alarm').upgrade()


def expirer():
    service.prepare_service()
    if cfg.CONF.database.time_to_live > 0:
        LOG.debug(_("Clearing expired metering data"))
        storage_conn = storage.get_connection_from_config(cfg.CONF)
        storage_conn.clear_expired_metering_data(
            cfg.CONF.database.time_to_live)
    else:
        LOG.info(_("Nothing to clean, database time to live is disabled"))
