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

from ceilometer import service
from ceilometer import storage

LOG = log.getLogger(__name__)


def upgrade():
    conf = cfg.ConfigOpts()
    conf.register_cli_opts([
        cfg.BoolOpt('skip-metering-database',
                    help='Skip metering database upgrade.',
                    default=False),
        cfg.BoolOpt('skip-gnocchi-resource-types',
                    help='Skip gnocchi resource-types upgrade.',
                    default=False),
    ])

    service.prepare_service(conf=conf)
    if conf.skip_metering_database:
        LOG.info("Skipping metering database upgrade")
    else:

        url = (getattr(conf.database, 'metering_connection') or
               conf.database.connection)
        if url:
            LOG.debug("Upgrading metering database")
            storage.get_connection(conf, url).upgrade()
        else:
            LOG.info("Skipping metering database upgrade, "
                     "legacy database backend not configured.")

    if conf.skip_gnocchi_resource_types:
        LOG.info("Skipping Gnocchi resource types upgrade")
    else:
        LOG.debug("Upgrading Gnocchi resource types")
        from ceilometer import gnocchi_client
        gnocchi_client.upgrade_resource_types(conf)


def expirer():
    conf = service.prepare_service()

    if conf.database.metering_time_to_live > 0:
        LOG.debug("Clearing expired metering data")
        storage_conn = storage.get_connection_from_config(conf)
        storage_conn.clear_expired_metering_data(
            conf.database.metering_time_to_live)
    else:
        LOG.info("Nothing to clean, database metering time to live "
                 "is disabled")


def db_clean_legacy():
    conf = cfg.ConfigOpts()
    conf.register_cli_opts([
        cfg.strOpt('confirm-drop-table',
                   short='n',
                   help='confirm to drop the legacy tables')])
    if not conf.confirm_drop_table:
        confirm = moves.input("Do you really want to drop the legacy "
                              "alarm and event tables? This will destroy "
                              "data definitively if it exist. Please type "
                              "'YES' to confirm: ")
        if confirm != 'YES':
            print("DB legacy cleanup aborted!")
            return

    service.prepare_service(conf=conf)

    url = (getattr(conf.database, "metering_connection") or
           conf.database.connection)
    parsed = urlparse.urlparse(url)

    if parsed.password:
        masked_netloc = '****'.join(parsed.netloc.rsplit(parsed.password))
        masked_url = parsed._replace(netloc=masked_netloc)
        masked_url = urlparse.urlunparse(masked_url)
    else:
        masked_url = url
    LOG.info('Starting to drop event, alarm and alarm history tables in '
             'backend: %s', masked_url)

    connection_scheme = parsed.scheme
    conn = storage.get_connection_from_config(conf)
    if connection_scheme in ('mysql', 'mysql+pymysql', 'postgresql',
                             'sqlite'):
        engine = conn._engine_facade.get_engine()
        meta = sa.MetaData(bind=engine)
        for table_name in ('alarm', 'alarm_history',
                           'trait_text', 'trait_int',
                           'trait_float', 'trait_datetime',
                           'event', 'event_type'):
            if engine.has_table(table_name):
                table = sa.Table(table_name, meta, autoload=True)
                table.drop()
                LOG.info("Legacy %s table of SQL backend has been "
                         "dropped.", table_name)
            else:
                LOG.info('%s table does not exist.', table_name)

    elif connection_scheme == 'hbase':
        with conn.conn_pool.connection() as h_conn:
            tables = h_conn.tables()
            table_name_mapping = {'alarm': 'alarm',
                                  'alarm_h': 'alarm history',
                                  'event': 'event'}
            for table_name in ('alarm', 'alarm_h', 'event'):
                try:
                    if table_name in tables:
                        h_conn.disable_table(table_name)
                        h_conn.delete_table(table_name)
                        LOG.info("Legacy %s table of Hbase backend "
                                 "has been dropped.",
                                 table_name_mapping[table_name])
                    else:
                        LOG.info('%s table does not exist.',
                                 table_name_mapping[table_name])
                except Exception as e:
                    LOG.error('Error occurred while dropping alarm '
                              'tables of Hbase, %s', e)

    elif connection_scheme == 'mongodb':
        for table_name in ('alarm', 'alarm_history', 'event'):
            if table_name in conn.db.conn.collection_names():
                conn.db.conn.drop_collection(table_name)
                LOG.info("Legacy %s table of Mongodb backend has been "
                         "dropped.", table_name)
            else:
                LOG.info('%s table does not exist.', table_name)
    LOG.info('Legacy alarm and event tables cleanup done.')
