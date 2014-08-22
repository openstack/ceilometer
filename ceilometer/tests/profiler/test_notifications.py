# Copyright 2014: Mirantis Inc.
# All Rights Reserved.
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
from oslotest import base

from ceilometer.profiler import notifications
from ceilometer import sample


NOTIFICATION = {
    "event_type": "profiler.compute",
    "message_id": "dae6f69c-00e0-41c0-b371-41ec3b7f4451",
    "publisher_id": "some_host",

    "payload": {
        "user_id": "1e3ce043029547f1a61c1996d1a531a2",
        "project_id": "663ce04332954555a61c1996d1a53143",
        "base_id": "2e3ce043029547f1a61c1996d1a531a2",
        "trace_id": "3e3ce043029547f1a61c1996d1a531a2",
        "parent_id": "4e3ce043029547f1a61c1996d1a531a2",
        "name": "some_name",
        "info": {
            "foo": "bar"
        }
    },
    "priority": "INFO",
    "timestamp": "2012-05-08 20:23:48.028195"
}


class ProfilerNotificationsTestCase(base.BaseTestCase):

    def test_process_notification(self):
        prof = notifications.ProfilerNotifications(None)
        info = next(prof.process_notification(NOTIFICATION))

        self.assertEqual(NOTIFICATION["payload"]["name"], info.name)
        self.assertEqual(sample.TYPE_GAUGE, info.type)
        self.assertEqual("trace", info.unit)
        self.assertEqual(NOTIFICATION["payload"]["user_id"], info.user_id)
        self.assertEqual(NOTIFICATION["payload"]["project_id"],
                         info.project_id)
        self.assertEqual("profiler-%s" % NOTIFICATION["payload"]["base_id"],
                         info.resource_id)
        self.assertEqual(1, info.volume)
        self.assertEqual(NOTIFICATION["timestamp"], info.timestamp)
        self.assertEqual(NOTIFICATION["payload"]["info"],
                         info.resource_metadata["info"])
        self.assertEqual(NOTIFICATION["publisher_id"],
                         info.resource_metadata["host"])
