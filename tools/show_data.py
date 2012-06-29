#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network (DreamHost)
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

import sys

from ceilometer import storage
from ceilometer.openstack.common import cfg


def show_users(db, args):
    for u in sorted(db.get_users()):
        print u


def show_resources(db, args):
    if args:
        users = args
    else:
        users = sorted(db.get_users())
    for u in users:
        print u
        for resource in db.get_resources(user=u):
            print '  %(resource_id)s %(timestamp)s' % resource
            for k, v in sorted(resource['metadata'].iteritems()):
                print '      %-10s : %s' % (k, v)
            for meter in resource['meter']:
                # FIXME(dhellmann): Need a way to tell whether to use
                # max() or sum() by meter name without hard-coding.
                if meter['counter_name'] in ['cpu', 'disk']:
                    totals = db.get_volume_max(storage.EventFilter(
                            user=u,
                            meter=meter['counter_name'],
                            resource=resource['resource_id'],
                            ))
                else:
                    totals = db.get_volume_sum(storage.EventFilter(
                            user=u,
                            meter=meter['counter_name'],
                            resource=resource['resource_id'],
                            ))
                print '    %s (%s): %s' % \
                    (meter['counter_name'], meter['counter_type'],
                     totals.next()['value'])


def show_total_resources(db, args):
    if args:
        users = args
    else:
        users = sorted(db.get_users())
    for u in users:
        print u
        for meter in ['disk', 'cpu', 'instance']:
            if meter in ['cpu', 'disk']:
                total = db.get_volume_max(storage.EventFilter(
                        user=u,
                        meter=meter,
                        ))
            else:
                total = db.get_volume_sum(storage.EventFilter(
                        user=u,
                        meter=meter,
                        ))
            for t in total:
                print '  ', meter, t['resource_id'], t['value']


def show_raw(db, args):
    fmt = '    %(timestamp)s %(counter_name)10s %(counter_volume)s'
    for u in sorted(db.get_users()):
        print u
        for resource in db.get_resources(user=u):
            print '  ', resource['resource_id']
            for event in db.get_raw_events(storage.EventFilter(
                    user=u,
                    resource=resource['resource_id'],
                    )):
                print fmt % event


def show_help(db, args):
    print 'COMMANDS:'
    for name in sorted(COMMANDS.keys()):
        print name


def show_projects(db, args):
    for u in sorted(db.get_projects()):
        print u


COMMANDS = {
    'users': show_users,
    'projects': show_projects,
    'help': show_help,
    'resources': show_resources,
    'total_resources': show_total_resources,
    'raw': show_raw,
    }


def main(argv):
    extra_args = cfg.CONF(
        sys.argv[1:],
        # NOTE(dhellmann): Read the configuration file(s) for the
        #ceilometer collector by default.
        default_config_files=['/etc/ceilometer-collector.conf'],
        )
    storage.register_opts(cfg.CONF)
    db = storage.get_connection(cfg.CONF)
    command = extra_args[0] if extra_args else 'help'
    COMMANDS[command](db, extra_args[1:])


if __name__ == '__main__':
    main(sys.argv)
