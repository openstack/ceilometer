#
# Copyright 2017 Huawei Technologies Co.,LTD.
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

"""Command line tool for migrating metrics data from ceilometer native
storage backend to Gnocchi.

Usage:
python migrate_data_to_gnocchi.py --native-metering-connection "mysql+pymysql:
//root:password@127.0.0.1/ceilometer?charset=utf8"

NOTE:
You may need to install *tqdm* python lib to support progress bar in migration.

"""

import sys

try:
    from tqdm import tqdm as progress_bar
except ImportError:
    progress_bar = None

import argparse
from oslo_config import cfg
from oslo_db import options as db_options
from oslo_log import log

from ceilometer.dispatcher import gnocchi
from ceilometer import service
from ceilometer import storage
from ceilometer.storage import impl_mongodb
from ceilometer.storage import impl_sqlalchemy
from ceilometer.storage.mongo import utils as pymongo_utils
from ceilometer import utils


def get_parser():
    parser = argparse.ArgumentParser(
        description='For migrating metrics data from ceilometer built-in '
                    'storage backends to Gnocchi.')
    parser.add_argument(
        '--native-metering-connection',
        required=True,
        help='The database connection url of native storage backend. '
             'e.g. mysql+pymysql://root:password@127.0.0.1/ceilometer?charset'
             '=utf8',
    )
    parser.add_argument(
        '--ceilometer-config-file',
        help="The config file of ceilometer, it is main used for gnocchi "
             "dispatcher to init gnocchiclient with the service credentials "
             "defined in the ceilometer config file. Default as "
             "/etc/ceilometer/ceilometer.conf",
    )
    parser.add_argument(
        '--log-file',
        default='gnocchi-data-migration.log',
        help="The log file to record messages during migration.", )
    parser.add_argument(
        '--batch-migration-size',
        default=300,
        help="The amount of samples that will be posted to gnocchi per batch",)
    parser.add_argument(
        '--start-timestamp',
        default=None,
        help="The stat timestamp of metrics data to be migrated, with ISO8601 "
             "format, e.g. 2016-01-25 11:58:00",
    )
    parser.add_argument(
        '--end-timestamp',
        default=None,
        help="The end timestamp of metrics data to be migrated, with ISO8601 "
             "format, e.g. 2017-01-25 11:58:00",
    )
    return parser


def count_samples(storage_conn, start_timestamp=None, end_timestamp=None):
    if start_timestamp:
        start_timestamp = utils.sanitize_timestamp(start_timestamp)
    if start_timestamp:
        end_timestamp = utils.sanitize_timestamp(end_timestamp)
    if isinstance(storage_conn, impl_sqlalchemy.Connection):
        from ceilometer.storage.sqlalchemy import models
        session = storage_conn._engine_facade.get_session()
        query = session.query(models.Sample.id)
        if start_timestamp:
            query = query.filter(models.Sample.timestamp >= start_timestamp)
        if end_timestamp:
            query = query.filter(models.Sample.timestamp < end_timestamp)
        return query.count()
    elif isinstance(storage_conn, impl_mongodb.Connection):
        ts_range = pymongo_utils.make_timestamp_range(start_timestamp,
                                                      end_timestamp)
        return storage_conn.db.meter.count(ts_range)
    else:
        print("Unsupported type of storage connection: %s" % storage_conn)
        sys.exit(1)


def get_native_storage_conn(metering_connection):
    storage_conf = cfg.ConfigOpts()
    db_options.set_defaults(storage_conf)
    storage_conf.register_opts(storage.OPTS, 'database')
    storage_conf.set_override('metering_connection',
                              metering_connection, 'database')
    storage_conn = storage.get_connection_from_config(storage_conf)
    return storage_conn


def main():
    args = get_parser().parse_args()

    storage_conn = get_native_storage_conn(args.native_metering_connection)
    total_amount = count_samples(storage_conn, args.start_timestamp,
                                 args.end_timestamp)
    print('%s samples will be migrated to Gnocchi.' % total_amount)

    # NOTE: we need service credentials to init gnocchiclient
    config_file = ([args.ceilometer_config_file] if
                   args.ceilometer_config_file else None)
    gnocchi_conf = service.prepare_service([], config_file)
    logger = log.getLogger()
    log_conf = cfg.ConfigOpts()
    log.register_options(log_conf)
    log_conf.set_override('log_file', args.log_file)
    log_conf.set_override('debug', True)
    log.setup(log_conf, 'ceilometer_migration')
    time_filters = []
    if args.start_timestamp:
        time_filters.append({">=": {'timestamp': args.start_timestamp}})
    if args.end_timestamp:
        time_filters.append({"<": {'timestamp': args.end_timestamp}})

    gnocchi_dispatcher = gnocchi.GnocchiDispatcher(gnocchi_conf)

    batch_size = args.batch_migration_size
    if total_amount == 'Unknown':
        total_amount = None
    orderby = [{"message_id": "asc"}]
    last_message_id = None
    migrated_amount = 0
    if progress_bar:
        pbar = progress_bar(total=total_amount, ncols=100, unit='samples')
    else:
        pbar = None
    while migrated_amount < total_amount:
        if time_filters and last_message_id:
            filter_expr = {
                'and': time_filters + [{">": {"message_id": last_message_id}}]}
        elif time_filters and not last_message_id:
            if len(time_filters) == 1:
                filter_expr = time_filters[0]
            else:
                filter_expr = {'and': time_filters}
        elif not time_filters and last_message_id:
            filter_expr = {">": {"message_id": last_message_id}}
        else:
            filter_expr = None
        samples = storage_conn.query_samples(
            filter_expr=filter_expr, orderby=orderby, limit=batch_size)
        samples = list(samples)
        if not samples:
            break
        last_message_id = samples[-1].message_id
        for sample in samples:
            logger.info('Migrating sample with message_id: %s, meter: %s, '
                        'resource_id: %s' % (sample.message_id,
                                             sample.counter_name,
                                             sample.resource_id))
        samples_dict = [sample.as_dict() for sample in samples]
        gnocchi_dispatcher.record_metering_data(samples_dict)
        length = len(samples)
        migrated_amount += length
        if pbar:
            pbar.update(length)
    logger.info("=========== %s metrics data migration done ============" %
                total_amount)

if __name__ == '__main__':
    sys.exit(main())
