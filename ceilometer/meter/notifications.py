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

import functools
import itertools
import os
import pkg_resources
import six
import yaml

from jsonpath_rw_ext import parser
from oslo_config import cfg
from oslo_log import log
import oslo_messaging

from ceilometer.agent import plugin_base
from ceilometer.i18n import _LE, _LW
from ceilometer import sample
from ceilometer import utils

OPTS = [
    cfg.StrOpt('meter_definitions_cfg_file',
               default="meters.yaml",
               help="Configuration file for defining meter notifications."
               ),
]

cfg.CONF.register_opts(OPTS, group='meter')
cfg.CONF.import_opt('disable_non_metric_meters', 'ceilometer.notification',
                    group='notification')

LOG = log.getLogger(__name__)


class MeterDefinitionException(Exception):
    def __init__(self, message, definition_cfg):
        super(MeterDefinitionException, self).__init__(message)
        self.message = message
        self.definition_cfg = definition_cfg

    def __str__(self):
        return '%s %s: %s' % (self.__class__.__name__,
                              self.definition_cfg, self.message)


class MeterDefinition(object):

    JSONPATH_RW_PARSER = parser.ExtentedJsonPathParser()

    REQUIRED_FIELDS = ['name', 'type', 'event_type', 'unit', 'volume',
                       'resource_id']

    def __init__(self, definition_cfg):
        self.cfg = definition_cfg
        missing = [field for field in self.REQUIRED_FIELDS
                   if not self.cfg.get(field)]
        if missing:
            raise MeterDefinitionException(
                _LE("Required fields %s not specified") % missing, self.cfg)
        self._event_type = self.cfg.get('event_type')
        if isinstance(self._event_type, six.string_types):
            self._event_type = [self._event_type]

        if ('type' not in self.cfg.get('lookup', []) and
                self.cfg['type'] not in sample.TYPES):
            raise MeterDefinitionException(
                _LE("Invalid type %s specified") % self.cfg['type'], self.cfg)

        self._field_getter = {}
        for name, field in self.cfg.items():
            if name in ["event_type", "lookup"] or not field:
                continue
            elif isinstance(field, six.integer_types):
                self._field_getter[name] = field
            elif isinstance(field, dict) and name == 'metadata':
                meta = {}
                for key, val in field.items():
                    parts = self.parse_jsonpath(val)
                    meta[key] = functools.partial(self._parse_jsonpath_field,
                                                  parts)
                self._field_getter['metadata'] = meta
            else:
                parts = self.parse_jsonpath(field)
                self._field_getter[name] = functools.partial(
                    self._parse_jsonpath_field, parts)

    def parse_jsonpath(self, field):
        try:
            parts = self.JSONPATH_RW_PARSER.parse(field)
        except Exception as e:
            raise MeterDefinitionException(_LE(
                "Parse error in JSONPath specification "
                "'%(jsonpath)s': %(err)s")
                % dict(jsonpath=field, err=e), self.cfg)
        return parts

    def match_type(self, meter_name):
        for t in self._event_type:
            if utils.match(meter_name, t):
                return True

    def parse_fields(self, field, message, all_values=False):
        getter = self._field_getter.get(field)
        if not getter:
            return
        elif isinstance(getter, dict):
            dict_val = {}
            for key, val in getter.items():
                dict_val[key] = val(message, all_values)
            return dict_val
        elif callable(getter):
            return getter(message, all_values)
        else:
            return getter

    @staticmethod
    def _parse_jsonpath_field(parts, message, all_values):
        values = [match.value for match in parts.find(message)
                  if match.value is not None]
        if values:
            if not all_values:
                return values[0]
            return values


def get_config_file():
    config_file = cfg.CONF.meter.meter_definitions_cfg_file
    if not os.path.exists(config_file):
        config_file = cfg.CONF.find_file(config_file)
    if not config_file:
        config_file = pkg_resources.resource_filename(
            __name__, "data/meters.yaml")
    return config_file


def setup_meters_config():
    """Setup the meters definitions from yaml config file."""
    config_file = get_config_file()
    if config_file is not None:
        LOG.debug(_LE("Meter Definitions configuration file: %s"), config_file)

        with open(config_file) as cf:
            config = cf.read()

        try:
            meters_config = yaml.safe_load(config)
        except yaml.YAMLError as err:
            if hasattr(err, 'problem_mark'):
                mark = err.problem_mark
                errmsg = (_LE("Invalid YAML syntax in Meter Definitions file "
                          "%(file)s at line: %(line)s, column: %(column)s.")
                          % dict(file=config_file,
                                 line=mark.line + 1,
                                 column=mark.column + 1))
            else:
                errmsg = (_LE("YAML error reading Meter Definitions file "
                          "%(file)s")
                          % dict(file=config_file))
            LOG.error(errmsg)
            raise

    else:
        LOG.debug(_LE("No Meter Definitions configuration file found!"
                  " Using default config."))
        meters_config = {}

    LOG.info(_LE("Meter Definitions: %s"), meters_config)

    return meters_config


def load_definitions(config_def):
    if not config_def:
        return []
    meter_defs = {}
    for event_def in reversed(config_def['metric']):
        if event_def.get('name') in meter_defs:
            # skip duplicate meters
            LOG.warning(_LW("Skipping duplicate meter definition %s")
                        % event_def)
            continue

        try:
            if (event_def.get('volume') != 1 or
                    not cfg.CONF.notification.disable_non_metric_meters):
                md = MeterDefinition(event_def)
                meter_defs[event_def['name']] = md
        except MeterDefinitionException as me:
            errmsg = (_LE("Error loading meter definition : %(err)s")
                      % dict(err=me.message))
            LOG.error(errmsg)
    return meter_defs.values()


class InvalidPayload(Exception):
    pass


class ProcessMeterNotifications(plugin_base.NotificationBase):

    event_types = []

    def __init__(self, manager):
        super(ProcessMeterNotifications, self).__init__(manager)
        self.definitions = load_definitions(setup_meters_config())

    def get_targets(self, conf):
        """Return a sequence of oslo_messaging.Target

        It is defining the exchange and topics to be connected for this plugin.
        :param conf: Configuration.
        #TODO(prad): This should be defined in the notification agent
        """
        targets = []
        exchanges = [
            conf.nova_control_exchange,
            conf.cinder_control_exchange,
            conf.glance_control_exchange,
            conf.neutron_control_exchange,
            conf.heat_control_exchange,
            conf.keystone_control_exchange,
            conf.sahara_control_exchange,
            conf.trove_control_exchange,
            conf.zaqar_control_exchange,
            conf.swift_control_exchange,
            conf.magnetodb_control_exchange,
            conf.ceilometer_control_exchange,
            conf.magnum_control_exchange,
            ]

        for exchange in exchanges:
            targets.extend(oslo_messaging.Target(topic=topic,
                                                 exchange=exchange)
                           for topic in
                           self.get_notification_topics(conf))
        return targets

    @staticmethod
    def _normalise_as_list(value, d, body, length):
        values = d.parse_fields(value, body, True)
        if not values:
            if value in d.cfg.get('lookup'):
                LOG.warning('Could not find %s values', value)
                raise InvalidPayload
            values = [d.cfg[value]]
        elif value in d.cfg.get('lookup') and length != len(values):
            LOG.warning('Not all fetched meters contain "%s" field', value)
            raise InvalidPayload
        return values if isinstance(values, list) else [values]

    def process_notification(self, notification_body):
        for d in self.definitions:
            if d.match_type(notification_body['event_type']):
                userid = self.get_user_id(d, notification_body)
                projectid = self.get_project_id(d, notification_body)
                resourceid = d.parse_fields('resource_id', notification_body)
                ts = d.parse_fields('timestamp', notification_body)
                metadata = d.parse_fields('metadata', notification_body)
                if d.cfg.get('lookup'):
                    meters = d.parse_fields('name', notification_body, True)
                    if not meters:  # skip if no meters in payload
                        break
                    try:
                        resources = self._normalise_as_list(
                            'resource_id', d, notification_body, len(meters))
                        volumes = self._normalise_as_list(
                            'volume', d, notification_body, len(meters))
                        units = self._normalise_as_list(
                            'unit', d, notification_body, len(meters))
                        types = self._normalise_as_list(
                            'type', d, notification_body, len(meters))
                        users = (self._normalise_as_list(
                            'user_id', d, notification_body, len(meters))
                            if 'user_id' in d.cfg['lookup'] else [userid])
                        projs = (self._normalise_as_list(
                            'project_id', d, notification_body, len(meters))
                            if 'project_id' in d.cfg['lookup']
                            else [projectid])
                        times = (self._normalise_as_list(
                            'timestamp', d, notification_body, len(meters))
                            if 'timestamp' in d.cfg['lookup'] else [ts])
                    except InvalidPayload:
                        break
                    for m, v, unit, t, r, p, user, ts in zip(
                            meters, volumes, itertools.cycle(units),
                            itertools.cycle(types), itertools.cycle(resources),
                            itertools.cycle(projs), itertools.cycle(users),
                            itertools.cycle(times)):
                        yield sample.Sample.from_notification(
                            name=m, type=t, unit=unit, volume=v,
                            resource_id=r, user_id=user, project_id=p,
                            message=notification_body, timestamp=ts,
                            metadata=metadata)
                else:
                    yield sample.Sample.from_notification(
                        name=d.cfg['name'],
                        type=d.cfg['type'],
                        unit=d.cfg['unit'],
                        volume=d.parse_fields('volume', notification_body),
                        resource_id=resourceid,
                        user_id=userid,
                        project_id=projectid,
                        message=notification_body,
                        timestamp=ts, metadata=metadata)

    @staticmethod
    def get_user_id(d, notification_body):
        return (d.parse_fields('user_id', notification_body) or
                notification_body.get('_context_user_id') or
                notification_body.get('_context_user', None))

    @staticmethod
    def get_project_id(d, notification_body):
        return (d.parse_fields('project_id', notification_body) or
                notification_body.get('_context_tenant_id') or
                notification_body.get('_context_tenant', None))
