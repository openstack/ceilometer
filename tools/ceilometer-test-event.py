#!/usr/bin/env python
#
# Copyright 2013 Rackspace Hosting.
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

"""Command line tool help you debug your event definitions.

Feed it a list of test notifications in json format, and it will show
you what events will be generated.
"""

import json
import sys

from oslo_config import cfg
from stevedore import extension

from ceilometer.event import converter
from ceilometer import service


cfg.CONF.register_cli_opts([
    cfg.StrOpt('input-file',
               short='i',
               help='File to read test notifications from.'
               ' (Containing a json list of notifications.)'
               ' defaults to stdin.'),
    cfg.StrOpt('output-file',
               short='o',
               help='File to write results to. Defaults to stdout.'),
])

TYPES = {1: 'text',
         2: 'int',
         3: 'float',
         4: 'datetime'}


service.prepare_service()

output_file = cfg.CONF.output_file
input_file = cfg.CONF.input_file

if output_file is None:
    out = sys.stdout
else:
    out = open(output_file, 'w')

if input_file is None:
    notifications = json.load(sys.stdin)
else:
    with open(input_file, 'r') as f:
        notifications = json.load(f)

out.write("Definitions file: %s\n" % cfg.CONF.event.definitions_cfg_file)
out.write("Notifications tested: %s\n" % len(notifications))

event_converter = converter.setup_events(
    extension.ExtensionManager(
        namespace='ceilometer.event.trait_plugin'))

for notification in notifications:
    event = event_converter.to_event(notification)
    if event is None:
        out.write("Dropped notification: %s\n" %
                  notification['message_id'])
        continue
    out.write("Event: %s at %s\n" % (event.event_type, event.generated))
    for trait in event.traits:
        dtype = TYPES[trait.dtype]
        out.write("    Trait: name: %s, type: %s, value: %s\n" % (
            trait.name, dtype, trait.value))
