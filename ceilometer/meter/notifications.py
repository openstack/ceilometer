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

import itertools
import pkg_resources
import six

from debtcollector import moves
from oslo_config import cfg
from oslo_log import log
import oslo_messaging
from stevedore import extension

from ceilometer.agent import plugin_base
from ceilometer import declarative
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


MeterDefinitionException = moves.moved_class(declarative.DefinitionException,
                                             'MeterDefinitionException',
                                             __name__,
                                             version=6.0,
                                             removal_version="?")


class MeterDefinition(object):

    SAMPLE_ATTRIBUTES = ["name", "type", "volume", "unit", "timestamp",
                         "user_id", "project_id", "resource_id"]

    REQUIRED_FIELDS = ['name', 'type', 'event_type', 'unit', 'volume',
                       'resource_id']

    def __init__(self, definition_cfg, plugin_manager):
        self.cfg = definition_cfg
        missing = [field for field in self.REQUIRED_FIELDS
                   if not self.cfg.get(field)]
        if missing:
            raise declarative.DefinitionException(
                _LE("Required fields %s not specified") % missing, self.cfg)

        self._event_type = self.cfg.get('event_type')
        if isinstance(self._event_type, six.string_types):
            self._event_type = [self._event_type]

        if ('type' not in self.cfg.get('lookup', []) and
                self.cfg['type'] not in sample.TYPES):
            raise declarative.DefinitionException(
                _LE("Invalid type %s specified") % self.cfg['type'], self.cfg)

        self._fallback_user_id = declarative.Definition(
            'user_id', "_context_user_id|_context_user", plugin_manager)
        self._fallback_project_id = declarative.Definition(
            'project_id', "_context_tenant_id|_context_tenant", plugin_manager)
        self._attributes = {}
        self._metadata_attributes = {}

        for name in self.SAMPLE_ATTRIBUTES:
            attr_cfg = self.cfg.get(name)
            if attr_cfg:
                self._attributes[name] = declarative.Definition(
                    name, attr_cfg, plugin_manager)
        metadata = self.cfg.get('metadata', {})
        for name in metadata:
            self._metadata_attributes[name] = declarative.Definition(
                name, metadata[name], plugin_manager)

        # List of fields we expected when multiple meter are in the payload
        self.lookup = self.cfg.get('lookup')
        if isinstance(self.lookup, six.string_types):
            self.lookup = [self.lookup]

    def match_type(self, meter_name):
        for t in self._event_type:
            if utils.match(meter_name, t):
                return True

    def to_samples(self, message, all_values=False):
        # Sample defaults
        sample = {
            'name': self.cfg["name"], 'type': self.cfg["type"],
            'unit': self.cfg["unit"], 'volume': None, 'timestamp': None,
            'user_id': self._fallback_user_id.parse(message),
            'project_id': self._fallback_project_id.parse(message),
            'resource_id': None, 'message': message, 'metadata': {},
        }
        for name, parser in self._metadata_attributes.items():
            value = parser.parse(message)
            if value:
                sample['metadata'][name] = value

        # NOTE(sileht): We expect multiple samples in the payload
        # so put each attribute into a list
        if self.lookup:
            for name in sample:
                sample[name] = [sample[name]]

        for name in self.SAMPLE_ATTRIBUTES:
            parser = self._attributes.get(name)
            if parser is not None:
                value = parser.parse(message, bool(self.lookup))
                # NOTE(sileht): If we expect multiple samples
                # some attributes are overridden even we don't get any
                # result. Also note in this case value is always a list
                if ((not self.lookup and value is not None) or
                        (self.lookup and ((name in self.lookup + ["name"])
                                          or value))):
                    sample[name] = value

        if self.lookup:
            nb_samples = len(sample['name'])
            # skip if no meters in payload
            if nb_samples <= 0:
                raise StopIteration

            attributes = self.SAMPLE_ATTRIBUTES + ["message", "metadata"]

            samples_values = []
            for name in attributes:
                values = sample.get(name)
                nb_values = len(values)
                if nb_values == nb_samples:
                    samples_values.append(values)
                elif nb_values == 1 and name not in self.lookup:
                    samples_values.append(itertools.cycle(values))
                else:
                    nb = (0 if nb_values == 1 and values[0] is None
                          else nb_values)
                    LOG.warning('Only %(nb)d fetched meters contain '
                                '"%(name)s" field instead of %(total)d.' %
                                dict(name=name, nb=nb,
                                     total=nb_samples))
                    raise StopIteration

            # NOTE(sileht): Transform the sample with multiple values per
            # attribute into multiple samples with one value per attribute.
            for values in zip(*samples_values):
                yield dict((attributes[idx], value)
                           for idx, value in enumerate(values))
        else:
            yield sample


class ProcessMeterNotifications(plugin_base.NotificationBase):

    event_types = []

    def __init__(self, manager):
        super(ProcessMeterNotifications, self).__init__(manager)
        self.definitions = self._load_definitions()

    @staticmethod
    def _load_definitions():
        plugin_manager = extension.ExtensionManager(
            namespace='ceilometer.event.trait_plugin')
        meters_cfg = declarative.load_definitions(
            {}, cfg.CONF.meter.meter_definitions_cfg_file,
            pkg_resources.resource_filename(__name__, "data/meters.yaml"))

        definitions = {}
        for meter_cfg in reversed(meters_cfg['metric']):
            if meter_cfg.get('name') in definitions:
                # skip duplicate meters
                LOG.warning(_LW("Skipping duplicate meter definition %s")
                            % meter_cfg)
                continue
            if (meter_cfg.get('volume') != 1
                    or not cfg.CONF.notification.disable_non_metric_meters):
                try:
                    md = MeterDefinition(meter_cfg, plugin_manager)
                except declarative.DefinitionException as me:
                    errmsg = (_LE("Error loading meter definition : %(err)s")
                              % dict(err=six.text_type(me)))
                    LOG.error(errmsg)
                else:
                    definitions[meter_cfg['name']] = md
        return definitions.values()

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
            conf.dns_control_exchange,
            ]

        for exchange in exchanges:
            targets.extend(oslo_messaging.Target(topic=topic,
                                                 exchange=exchange)
                           for topic in
                           self.get_notification_topics(conf))
        return targets

    def process_notification(self, notification_body):
        for d in self.definitions:
            if d.match_type(notification_body['event_type']):
                for s in d.to_samples(notification_body):
                    yield sample.Sample.from_notification(**s)
