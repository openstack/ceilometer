#
# Copyright 2013 IBM Corp
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

from oslo_log import log
from oslo_utils import timeutils

from ceilometer import dispatcher
from ceilometer import storage

LOG = log.getLogger(__name__)


class MeterDatabaseDispatcher(dispatcher.MeterDispatcherBase):
    """Dispatcher class for recording metering data into database.

    The dispatcher class which records each meter into a database configured
    in ceilometer configuration file.

    To enable this dispatcher, the following section needs to be present in
    ceilometer.conf file

    [DEFAULT]
    meter_dispatchers = database
    """

    @property
    def conn(self):
        if not hasattr(self, "_conn"):
            self._conn = storage.get_connection_from_config(
                self.conf)
        return self._conn

    def record_metering_data(self, data):
        # We may have receive only one counter on the wire
        if not data:
            return
        if not isinstance(data, list):
            data = [data]

        for meter in data:
            LOG.debug(
                'metering data %(counter_name)s '
                'for %(resource_id)s @ %(timestamp)s: %(counter_volume)s',
                {'counter_name': meter['counter_name'],
                 'resource_id': meter['resource_id'],
                 'timestamp': meter.get('timestamp', 'NO TIMESTAMP'),
                 'counter_volume': meter['counter_volume']})
            # Convert the timestamp to a datetime instance.
            # Storage engines are responsible for converting
            # that value to something they can store.
            if meter.get('timestamp'):
                ts = timeutils.parse_isotime(meter['timestamp'])
                meter['timestamp'] = timeutils.normalize_time(ts)
        try:
            self.conn.record_metering_data_batch(data)
        except Exception as err:
            LOG.error('Failed to record %(len)s: %(err)s.',
                      {'len': len(data), 'err': err})
            raise
