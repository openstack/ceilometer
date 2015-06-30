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

from oslo_config import cfg

from ceilometer.i18n import _LI
from ceilometer import service
from ceilometer import storage


LOG = logging.getLogger(__name__)


def dbsync():
    service.prepare_service()
    storage.get_connection_from_config(cfg.CONF, 'metering').upgrade()
    storage.get_connection_from_config(cfg.CONF, 'event').upgrade()


def expirer():
    service.prepare_service()

    if cfg.CONF.database.metering_time_to_live > 0:
        LOG.debug("Clearing expired metering data")
        storage_conn = storage.get_connection_from_config(cfg.CONF, 'metering')
        storage_conn.clear_expired_metering_data(
            cfg.CONF.database.metering_time_to_live)
    else:
        LOG.info(_LI("Nothing to clean, database metering time to live "
                     "is disabled"))

    if cfg.CONF.database.event_time_to_live > 0:
        LOG.debug("Clearing expired event data")
        event_conn = storage.get_connection_from_config(cfg.CONF, 'event')
        event_conn.clear_expired_event_data(
            cfg.CONF.database.event_time_to_live)
    else:
        LOG.info(_LI("Nothing to clean, database event time to live "
                     "is disabled"))
