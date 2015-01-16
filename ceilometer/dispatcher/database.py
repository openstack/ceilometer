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
from oslo_utils import timeutils

from ceilometer import dispatcher
from ceilometer.i18n import _
from ceilometer.openstack.common import log
from ceilometer.publisher import utils as publisher_utils
from ceilometer import storage

LOG = log.getLogger(__name__)


class DatabaseDispatcher(dispatcher.Base):
    """Dispatcher class for recording metering data into database.

    The dispatcher class which records each meter into a database configured
    in ceilometer configuration file.

    To enable this dispatcher, the following section needs to be present in
    ceilometer.conf file

    dispatchers = database
    """
    def __init__(self, conf):
        super(DatabaseDispatcher, self).__init__(conf)

        self._meter_conn = self._get_db_conn('metering', True)
        self._event_conn = self._get_db_conn('event', True)

    def _get_db_conn(self, purpose, ignore_exception=False):
        try:
            return storage.get_connection_from_config(self.conf, purpose)
        except Exception as err:
            params = {"purpose": purpose, "err": err}
            LOG.exception(_("Failed to connect to db, purpose %(purpose)s "
                            "re-try later: %(err)s") % params)
            if not ignore_exception:
                raise

    @property
    def meter_conn(self):
        if not self._meter_conn:
            self._meter_conn = self._get_db_conn('metering')

        return self._meter_conn

    @property
    def event_conn(self):
        if not self._event_conn:
            self._event_conn = self._get_db_conn('event')

        return self._event_conn

    def record_metering_data(self, data):
        # We may have receive only one counter on the wire
        if not isinstance(data, list):
            data = [data]

        for meter in data:
            LOG.debug(_(
                'metering data %(counter_name)s '
                'for %(resource_id)s @ %(timestamp)s: %(counter_volume)s')
                % ({'counter_name': meter['counter_name'],
                    'resource_id': meter['resource_id'],
                    'timestamp': meter.get('timestamp', 'NO TIMESTAMP'),
                    'counter_volume': meter['counter_volume']}))
            if publisher_utils.verify_signature(
                    meter, self.conf.publisher.telemetry_secret):
                try:
                    # Convert the timestamp to a datetime instance.
                    # Storage engines are responsible for converting
                    # that value to something they can store.
                    if meter.get('timestamp'):
                        ts = timeutils.parse_isotime(meter['timestamp'])
                        meter['timestamp'] = timeutils.normalize_time(ts)
                    self.meter_conn.record_metering_data(meter)
                except Exception as err:
                    LOG.exception(_('Failed to record metering data: %s'),
                                  err)
            else:
                LOG.warning(_(
                    'message signature invalid, discarding message: %r'),
                    meter)

    def record_events(self, events):
        if not isinstance(events, list):
            events = [events]

        return self.event_conn.record_events(events)
