#!/usr/bin/env python
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

"""Command line tool for creating event test data for Ceilometer.

Usage:

Generate testing data for e.g. for default time span

source .tox/py27/bin/activate
./tools/make_test_event_data.py --event_types 3
"""
import argparse
import datetime
import logging
import random
import sys
import uuid

from oslo_config import cfg
from oslo_utils import timeutils

from ceilometer.event.storage import models
from ceilometer import storage


def make_test_data(conn, start, end, interval, event_types):

    # Compute start and end timestamps for the new data.
    if isinstance(start, datetime.datetime):
        timestamp = start
    else:
        timestamp = timeutils.parse_strtime(start)

    if not isinstance(end, datetime.datetime):
        end = timeutils.parse_strtime(end)

    increment = datetime.timedelta(minutes=interval)

    print('Adding new events')
    n = 0
    while timestamp <= end:
        data = []
        for i in range(event_types):
            traits = [models.Trait('id1_%d' % i, 1, str(uuid.uuid4())),
                      models.Trait('id2_%d' % i, 2, random.randint(1, 10)),
                      models.Trait('id3_%d' % i, 3, random.random()),
                      models.Trait('id4_%d' % i, 4, timestamp)]
            data.append(models.Event(str(uuid.uuid4()),
                                     'event_type%d' % i,
                                     timestamp,
                                     traits,
                                     {}))
            n += 1
        conn.record_events(data)
        timestamp = timestamp + increment
    print('Added %d new events' % n)


def main():
    cfg.CONF([], project='ceilometer')

    parser = argparse.ArgumentParser(
        description='generate event data',
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
        type=int,
        help='The number of days in the past to start timestamps.',
    )
    parser.add_argument(
        '--end',
        default=2,
        type=int,
        help='The number of days into the future to continue timestamps.',
    )
    parser.add_argument(
        '--event_types',
        default=3,
        type=int,
        help='The number of unique event_types.',
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

    # Connect to the event database
    conn = storage.get_connection_from_config(cfg.CONF, 'event')

    # Compute the correct time span
    start = datetime.datetime.utcnow() - datetime.timedelta(days=args.start)
    end = datetime.datetime.utcnow() + datetime.timedelta(days=args.end)

    make_test_data(conn=conn,
                   start=start,
                   end=end,
                   interval=args.interval,
                   event_types=args.event_types)


if __name__ == '__main__':
    main()
