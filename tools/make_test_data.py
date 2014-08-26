#!/usr/bin/env python
#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

"""Command line tool for creating test data for Ceilometer.

Usage:

Generate testing data for e.g. for default time span

source .tox/py27/bin/activate
./tools/make_test_data.py --user 1 --project 1 1 cpu_util 20
"""
from __future__ import print_function

import argparse
import datetime
import logging
import random
import sys

from oslo.config import cfg
from oslo.utils import timeutils

from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer import storage


def make_test_data(conn, name, meter_type, unit, volume, random_min,
                   random_max, user_id, project_id, resource_id, start,
                   end, interval, resource_metadata={}, source='artificial',):

    # Compute start and end timestamps for the new data.
    if isinstance(start, datetime.datetime):
        timestamp = start
    else:
        timestamp = timeutils.parse_strtime(start)

    if not isinstance(end, datetime.datetime):
        end = timeutils.parse_strtime(end)

    increment = datetime.timedelta(minutes=interval)


    print('Adding new events for meter %s.' % (name))
    # Generate events
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
                          timestamp=timestamp,
                          resource_metadata=resource_metadata,
                          source=source,
                          )
        data = utils.meter_message_from_counter(
            c,
            cfg.CONF.publisher.metering_secret)
        conn.record_metering_data(data)
        n += 1
        timestamp = timestamp + increment

        if (meter_type == 'gauge' or meter_type == 'delta'):
            # For delta and gauge, we don't want to increase the value
            # in time by random element. So we always set it back to
            # volume.
            total_volume = volume

    print('Added %d new events for meter %s.' % (n, name))


def main():
    cfg.CONF([], project='ceilometer')

    parser = argparse.ArgumentParser(
        description='generate metering data',
    )
    parser.add_argument(
        '--interval',
        default=10,
        type=int,
        help='The period between events, in minutes.',
    )
    parser.add_argument(
        '--start',
        default=31,
        help='The number of days in the past to start timestamps.',
    )
    parser.add_argument(
        '--end',
        default=2,
        help='The number of days into the future to continue timestamps.',
    )
    parser.add_argument(
        '--type',
        choices=('gauge', 'cumulative'),
        default='gauge',
        help='Counter type.',
    )
    parser.add_argument(
        '--unit',
        default=None,
        help='Counter unit.',
    )
    parser.add_argument(
        '--project',
        help='Project id of owner.',
    )
    parser.add_argument(
        '--user',
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
        'resource',
        help='The resource id for the meter data.',
    )
    parser.add_argument(
        'counter',
        help='The counter name for the meter data.',
    )
    parser.add_argument(
        'volume',
        help='The amount to attach to the meter.',
        type=int,
        default=1,
    )
    args = parser.parse_args()

    # Set up logging to use the console
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')
    console.setFormatter(formatter)
    root_logger = logging.getLogger('')
    root_logger.addHandler(console)
    root_logger.setLevel(logging.DEBUG)

    # Connect to the metering database
    conn = storage.get_connection_from_config(cfg.CONF)

    # Find the user and/or project for a real resource
    if not (args.user or args.project):
        for r in conn.get_resources():
            if r.resource_id == args.resource:
                args.user = r.user_id
                args.project = r.project_id
                break

    # Compute the correct time span
    start = datetime.datetime.utcnow() - datetime.timedelta(days=args.start)
    end = datetime.datetime.utcnow() + datetime.timedelta(days=args.end)

    make_test_data(conn = conn,
                   name=args.counter,
                   meter_type=args.type,
                   unit=args.unit,
                   volume=args.volume,
                   random_min=args.random_min,
                   random_max=args.random_max,
                   user_id=args.user,
                   project_id=args.project,
                   resource_id=args.resource,
                   start=start,
                   end=end,
                   interval=args.interval,
                   resource_metadata={},
                   source='artificial',)

    return 0

if __name__ == '__main__':
    main()
