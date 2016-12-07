#!/usr/bin/env python
#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

"""Command line tool for creating test data for Ceilometer.

Usage:

Generate testing data for e.g. for default time span

source .tox/py27/bin/activate
./tools/make_test_data.py --user 1 --project 1 --resource 1 --counter cpu_util
--volume 20
"""
import argparse
import datetime
import random
import uuid

from oslo_utils import timeutils

from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer import service
from ceilometer import storage


def make_test_data(conf, name, meter_type, unit, volume, random_min,
                   random_max, user_id, project_id, resource_id, start,
                   end, interval, resource_metadata=None, source='artificial'):
    resource_metadata = resource_metadata or {'display_name': 'toto',
                                              'host': 'tata',
                                              'image_ref': 'test',
                                              'instance_flavor_id': 'toto',
                                              'server_group': 'toto',
                                              }
    # Compute start and end timestamps for the new data.
    if isinstance(start, datetime.datetime):
        timestamp = start
    else:
        timestamp = timeutils.parse_strtime(start)

    if not isinstance(end, datetime.datetime):
        end = timeutils.parse_strtime(end)

    increment = datetime.timedelta(minutes=interval)

    print('Adding new samples for meter %s.' % (name))
    # Generate samples
    n = 0
    total_volume = volume
    while timestamp <= end:
        if (random_min >= 0 and random_max >= 0):
            # If there is a random element defined, we will add it to
            # user given volume.
            if isinstance(random_min, int) and isinstance(random_max, int):
                total_volume += random.randint(random_min, random_max)
            else:
                total_volume += random.uniform(random_min, random_max)

        c = sample.Sample(name=name,
                          type=meter_type,
                          unit=unit,
                          volume=total_volume,
                          user_id=user_id,
                          project_id=project_id,
                          resource_id=resource_id,
                          timestamp=timestamp.isoformat(),
                          resource_metadata=resource_metadata,
                          source=source,
                          )
        data = utils.meter_message_from_counter(
            c, conf.publisher.telemetry_secret)
        # timestamp should be string when calculating signature, but should be
        # datetime object when calling record_metering_data.
        data['timestamp'] = timestamp
        yield data
        n += 1
        timestamp = timestamp + increment

        if (meter_type == 'gauge' or meter_type == 'delta'):
            # For delta and gauge, we don't want to increase the value
            # in time by random element. So we always set it back to
            # volume.
            total_volume = volume

    print('Added %d new samples for meter %s.' % (n, name))


def record_test_data(conf, conn, *args, **kwargs):
    for data in make_test_data(conf, *args, **kwargs):
        conn.record_metering_data(data)


def get_parser():
    parser = argparse.ArgumentParser(
        description='generate metering data',
    )
    parser.add_argument(
        '--interval',
        default=10,
        type=int,
        help='The period between samples, in minutes.',
    )
    parser.add_argument(
        '--start',
        default=31,
        help='Number of days to be stepped back from now or date in the past ('
             '"YYYY-MM-DDTHH:MM:SS" format) to define timestamps start range.',
    )
    parser.add_argument(
        '--end',
        default=2,
        help='Number of days to be stepped forward from now or date in the '
             'future ("YYYY-MM-DDTHH:MM:SS" format) to define timestamps end '
             'range.',
    )
    parser.add_argument(
        '--type',
        choices=('gauge', 'cumulative'),
        default='gauge',
        dest='meter_type',
        help='Counter type.',
    )
    parser.add_argument(
        '--unit',
        default=None,
        help='Counter unit.',
    )
    parser.add_argument(
        '--project',
        dest='project_id',
        help='Project id of owner.',
    )
    parser.add_argument(
        '--user',
        dest='user_id',
        help='User id of owner.',
    )
    parser.add_argument(
        '--random_min',
        help='The random min border of amount for added to given volume.',
        type=int,
        default=0,
    )
    parser.add_argument(
        '--random_max',
        help='The random max border of amount for added to given volume.',
        type=int,
        default=0,
    )
    parser.add_argument(
        '--resource',
        dest='resource_id',
        default=str(uuid.uuid4()),
        help='The resource id for the meter data.',
    )
    parser.add_argument(
        '--counter',
        default='instance',
        dest='name',
        help='The counter name for the meter data.',
    )
    parser.add_argument(
        '--volume',
        help='The amount to attach to the meter.',
        type=int,
        default=1,
    )
    return parser


def main():

    args = get_parser().parse_args()
    conf = service.prepare_service([])

    # Connect to the metering database
    conn = storage.get_connection_from_config(conf)

    # Find the user and/or project for a real resource
    if not (args.user_id or args.project_id):
        for r in conn.get_resources():
            if r.resource_id == args.resource_id:
                args.user_id = r.user_id
                args.project_id = r.project_id
                break

    # Compute the correct time span
    format = '%Y-%m-%dT%H:%M:%S'

    try:
        start = datetime.datetime.utcnow() - datetime.timedelta(
            days=int(args.start))
    except ValueError:
        try:
            start = datetime.datetime.strptime(args.start, format)
        except ValueError:
            raise

    try:
        end = datetime.datetime.utcnow() + datetime.timedelta(
            days=int(args.end))
    except ValueError:
        try:
            end = datetime.datetime.strptime(args.end, format)
        except ValueError:
            raise
    args.start = start
    args.end = end
    record_test_data(conf, conn=conn, **args.__dict__)

    return 0


if __name__ == '__main__':
    main()
