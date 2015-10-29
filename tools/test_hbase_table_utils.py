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

import os
import sys

from oslo_config import cfg

from ceilometer import storage


def main(argv):
    cfg.CONF([], project='ceilometer')
    if os.getenv("CEILOMETER_TEST_STORAGE_URL", "").startswith("hbase://"):
        url = ("%s?table_prefix=%s" %
               (os.getenv("CEILOMETER_TEST_STORAGE_URL"),
                os.getenv("CEILOMETER_TEST_HBASE_TABLE_PREFIX", "test")))
        conn = storage.get_connection(url, 'ceilometer.metering.storage')
        event_conn = storage.get_connection(url, 'ceilometer.event.storage')
        for arg in argv:
            if arg == "--upgrade":
                conn.upgrade()
                event_conn.upgrade()
            if arg == "--clear":
                conn.clear()
                event_conn.clear()


if __name__ == '__main__':
    main(sys.argv[1:])
