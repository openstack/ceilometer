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
from oslo_log import log
from six import moves
import six.moves.urllib.parse as urlparse
import sqlalchemy as sa

from ceilometer.i18n import _LE, _LI
from ceilometer import service
from ceilometer import storage

LOG = log.getLogger(__name__)


def upgrade():
    cfg.CONF.register_cli_opts([
        cfg.BoolOpt('skip-metering-database',
                    help='Skip metering database upgrade.',
                    default=False),
        cfg.BoolOpt('skip-event-database',
                    help='Skip event database upgrade.',
                    default=False),
        cfg.BoolOpt('skip-gnocchi-resource-types',
                    help='Skip gnocchi resource-types upgrade.',
                    default=False),
    ])

    service.prepare_service()
    if cfg.CONF.skip_metering_database:
        LOG.info("Skipping metering database upgrade")
    else:
        LOG.debug("Upgrading metering database")
        storage.get_connection_from_config(cfg.CONF, 'metering').upgrade()

    if cfg.CONF.skip_event_database:
        LOG.info("Skipping event database upgrade")
    else:
        LOG.debug("Upgrading event database")
        storage.get_connection_from_config(cfg.CONF, 'event').upgrade()

    if cfg.CONF.skip_gnocchi_resource_types:
        LOG.info("Skipping Gnocchi resource types upgrade")
    else:
        LOG.debug("Upgrading Gnocchi resource types")
        from ceilometer import gnocchi_client
        gnocchi_client.upgrade_resource_types(cfg.CONF)


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


def db_clean_legacy():
    cfg.CONF.register_cli_opts([
        cfg.StrOpt('confirm-drop-alarm-table',
                   short='n',
                   help='confirm to drop the legacy alarm tables')])
    if not cfg.CONF.confirm_drop_alarm_table:
        confirm = moves.input("Do you really want to drop the legacy alarm "
                              "tables? This will destroy data definitely "
                              "if it exist. Please type 'YES' to confirm: ")
        if confirm != 'YES':
            print("DB legacy cleanup aborted!")
            return

    service.prepare_service()
    for purpose in ['metering', 'event']:
        url = (getattr(cfg.CONF.database, '%s_connection' % purpose) or
               cfg.CONF.database.connection)
        parsed = urlparse.urlparse(url)

        if parsed.password:
            masked_netloc = '****'.join(parsed.netloc.rsplit(parsed.password))
            masked_url = parsed._replace(netloc=masked_netloc)
            masked_url = urlparse.urlunparse(masked_url)
        else:
            masked_url = url
        LOG.info(_LI('Starting to drop alarm and alarm history tables in '
                     '%(purpose)s backend: %(url)s'), {
            'purpose': purpose, 'url': masked_url})

        connection_scheme = parsed.scheme
        conn = storage.get_connection_from_config(cfg.CONF, purpose)
        if connection_scheme in ('mysql', 'mysql+pymysql', 'postgresql',
                                 'sqlite'):
            engine = conn._engine_facade.get_engine()
            meta = sa.MetaData(bind=engine)
            for table_name in ['alarm', 'alarm_history']:
                if engine.has_table(table_name):
                    alarm = sa.Table(table_name, meta, autoload=True)
                    alarm.drop()
                    LOG.info(_LI("Legacy %s table of SQL backend has been "
                                 "dropped."), table_name)
                else:
                    LOG.info(_LI('%s table does not exist.'), table_name)

        elif connection_scheme == 'hbase':
            with conn.conn_pool.connection() as h_conn:
                tables = h_conn.tables()
                table_name_mapping = {'alarm': 'alarm',
                                      'alarm_h': 'alarm history'}
                for table_name in ['alarm', 'alarm_h']:
                    try:
                        if table_name in tables:
                            h_conn.disable_table(table_name)
                            h_conn.delete_table(table_name)
                            LOG.info(_LI("Legacy %s table of Hbase backend "
                                         "has been dropped."),
                                     table_name_mapping[table_name])
                        else:
                            LOG.info(_LI('%s table does not exist.'),
                                     table_name_mapping[table_name])
                    except Exception as e:
                        LOG.error(_LE('Error occurred while dropping alarm '
                                      'tables of Hbase, %s'), e)

        elif connection_scheme == 'mongodb':
            for table_name in ['alarm', 'alarm_history']:
                if table_name in conn.db.conn.collection_names():
                    conn.db.conn.drop_collection(table_name)
                    LOG.info(_LI("Legacy %s table of Mongodb backend has been "
                                 "dropped."), table_name)
                else:
                    LOG.info(_LI('%s table does not exist.'), table_name)
    LOG.info('Legacy alarm tables cleanup done.')
