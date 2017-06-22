#
# Copyright 2014 Red Hat
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
"""Converters for producing hardware sensor data sample messages from
notification events.
"""

from oslo_config import cfg
from oslo_log import log
import oslo_messaging as messaging

from ceilometer.agent import plugin_base
from ceilometer import sample

LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('ironic_exchange',
               default='ironic',
               help='Exchange name for Ironic notifications.'),
]


# Map unit name to SI
UNIT_MAP = {
    'Watts': 'W',
    'Volts': 'V',
}


def validate_reading(data):
    """Some sensors read "Disabled"."""
    return data != 'Disabled'


def transform_id(data):
    return data.lower().replace(' ', '_')


def parse_reading(data):
    try:
        volume, unit = data.split(' ', 1)
        unit = unit.rsplit(' ', 1)[-1]
        return float(volume), UNIT_MAP.get(unit, unit)
    except ValueError:
        raise InvalidSensorData('unable to parse sensor reading: %s' %
                                data)


class InvalidSensorData(ValueError):
    pass


class SensorNotification(plugin_base.NotificationBase):
    """A generic class for extracting samples from sensor data notifications.

    A notification message can contain multiple samples from multiple
    sensors, all with the same basic structure: the volume for the sample
    is found as part of the value of a 'Sensor Reading' key. The unit
    is in the same value.

    Subclasses exist solely to allow flexibility with stevedore configuration.
    """

    event_types = ['hardware.ipmi.*']
    metric = None

    def get_targets(self, conf):
        """oslo.messaging.TargetS for this plugin."""
        return [messaging.Target(topic=topic,
                                 exchange=conf.ironic_exchange)
                for topic in self.get_notification_topics(conf)]

    def _get_sample(self, message):
        try:
            return (payload for _, payload
                    in message['payload'][self.metric].items())
        except KeyError:
            return []

    @staticmethod
    def _package_payload(message, payload):
        # NOTE(chdent): How much of the payload should we keep?
        # FIXME(gordc): ironic adds timestamp and event_type in its payload
        # which we are using below. we should probably just use oslo.messaging
        # values instead?
        payload['node'] = message['payload']['node_uuid']
        info = {'publisher_id': message['publisher_id'],
                'timestamp': message['payload']['timestamp'],
                'event_type': message['payload']['event_type'],
                'user_id': message['payload'].get('user_id'),
                'project_id': message['payload'].get('project_id'),
                'payload': payload}
        return info

    def process_notification(self, message):
        """Read and process a notification.

        The guts of a message are in dict value of a 'payload' key
        which then itself has a payload key containing a dict of
        multiple sensor readings.

        If expected keys in the payload are missing or values
        are not in the expected form for transformations,
        KeyError and ValueError are caught and the current
        sensor payload is skipped.
        """
        payloads = self._get_sample(message['payload'])
        for payload in payloads:
            try:
                # Provide a fallback resource_id in case parts are missing.
                resource_id = 'missing id'
                try:
                    resource_id = '%(nodeid)s-%(sensorid)s' % {
                        'nodeid': message['payload']['node_uuid'],
                        'sensorid': transform_id(payload['Sensor ID'])
                    }
                except KeyError as exc:
                    raise InvalidSensorData('missing key in payload: %s' % exc)

                info = self._package_payload(message, payload)

                try:
                    sensor_reading = info['payload']['Sensor Reading']
                except KeyError as exc:
                    raise InvalidSensorData(
                        "missing 'Sensor Reading' in payload"
                    )

                if validate_reading(sensor_reading):
                    volume, unit = parse_reading(sensor_reading)
                    yield sample.Sample.from_notification(
                        name='hardware.ipmi.%s' % self.metric.lower(),
                        type=sample.TYPE_GAUGE,
                        unit=unit,
                        volume=volume,
                        resource_id=resource_id,
                        message=info,
                        user_id=info['user_id'],
                        project_id=info['project_id'],
                        timestamp=info['timestamp'])

            except InvalidSensorData as exc:
                LOG.warning(
                    'invalid sensor data for %(resource)s: %(error)s' %
                    dict(resource=resource_id, error=exc)
                )
                continue


class TemperatureSensorNotification(SensorNotification):
    metric = 'Temperature'


class CurrentSensorNotification(SensorNotification):
    metric = 'Current'


class FanSensorNotification(SensorNotification):
    metric = 'Fan'


class VoltageSensorNotification(SensorNotification):
    metric = 'Voltage'
