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

from oslo_config import cfg
from oslo_log import log
from oslo_utils import fnmatch
from oslo_utils import timeutils
import pkg_resources
import six

from ceilometer import declarative
from ceilometer.event.storage import models
from ceilometer.i18n import _

OPTS = [
    cfg.StrOpt('definitions_cfg_file',
               default="event_definitions.yaml",
               help="Configuration file for event definitions."
               ),
    cfg.BoolOpt('drop_unmatched_notifications',
                default=False,
                help='Drop notifications if no event definition matches. '
                '(Otherwise, we convert them with just the default traits)'),
    cfg.MultiStrOpt('store_raw',
                    default=[],
                    help='Store the raw notification for select priority '
                    'levels (info and/or error). By default, raw details are '
                    'not captured.')
]

LOG = log.getLogger(__name__)


class TraitDefinition(declarative.Definition):
    def __init__(self, name, trait_cfg, plugin_manager):
        super(TraitDefinition, self).__init__(name, trait_cfg, plugin_manager)
        type_name = (trait_cfg.get('type', 'text')
                     if isinstance(trait_cfg, dict) else 'text')
        self.trait_type = models.Trait.get_type_by_name(type_name)
        if self.trait_type is None:
            raise declarative.EventDefinitionException(
                _("Invalid trait type '%(type)s' for trait %(trait)s")
                % dict(type=type_name, trait=name), self.cfg)

    def to_trait(self, notification_body):
        value = self.parse(notification_body)
        if value is None:
            return None

        # NOTE(mdragon): some openstack projects (mostly Nova) emit ''
        # for null fields for things like dates.
        if self.trait_type != models.Trait.TEXT_TYPE and value == '':
            return None

        value = models.Trait.convert_value(self.trait_type, value)
        return models.Trait(self.name, self.trait_type, value)


class EventDefinition(object):

    DEFAULT_TRAITS = dict(
        service=dict(type='text', fields='publisher_id'),
        request_id=dict(type='text', fields='ctxt.request_id'),
        project_id=dict(type='text', fields=['payload.tenant_id',
                                             'ctxt.tenant']),
        user_id=dict(type='text', fields=['payload.user_id',
                                          'ctxt.user_id']),
        # TODO(dikonoor):tenant_id is old terminology and should
        # be deprecated
        tenant_id=dict(type='text', fields=['payload.tenant_id',
                                            'ctxt.tenant']),
    )

    def __init__(self, definition_cfg, trait_plugin_mgr, raw_levels):
        self._included_types = []
        self._excluded_types = []
        self.traits = dict()
        self.cfg = definition_cfg
        self.raw_levels = raw_levels

        try:
            event_type = definition_cfg['event_type']
            traits = definition_cfg['traits']
        except KeyError as err:
            raise declarative.EventDefinitionException(
                _("Required field %s not specified") % err.args[0], self.cfg)

        if isinstance(event_type, six.string_types):
            event_type = [event_type]

        for t in event_type:
            if t.startswith('!'):
                self._excluded_types.append(t[1:])
            else:
                self._included_types.append(t)

        if self._excluded_types and not self._included_types:
            self._included_types.append('*')

        for trait_name in self.DEFAULT_TRAITS:
            self.traits[trait_name] = TraitDefinition(
                trait_name,
                self.DEFAULT_TRAITS[trait_name],
                trait_plugin_mgr)
        for trait_name in traits:
            self.traits[trait_name] = TraitDefinition(
                trait_name,
                traits[trait_name],
                trait_plugin_mgr)

    def included_type(self, event_type):
        for t in self._included_types:
            if fnmatch.fnmatch(event_type, t):
                return True
        return False

    def excluded_type(self, event_type):
        for t in self._excluded_types:
            if fnmatch.fnmatch(event_type, t):
                return True
        return False

    def match_type(self, event_type):
        return (self.included_type(event_type)
                and not self.excluded_type(event_type))

    @property
    def is_catchall(self):
        return '*' in self._included_types and not self._excluded_types

    def to_event(self, priority, notification_body):
        event_type = notification_body['event_type']
        message_id = notification_body['metadata']['message_id']
        when = timeutils.normalize_time(timeutils.parse_isotime(
            notification_body['metadata']['timestamp']))

        traits = (self.traits[t].to_trait(notification_body)
                  for t in self.traits)
        # Only accept non-None value traits ...
        traits = [trait for trait in traits if trait is not None]
        raw = notification_body if priority in self.raw_levels else {}
        event = models.Event(message_id, event_type, when, traits, raw)
        return event


class NotificationEventsConverter(object):
    """Notification Event Converter

    The NotificationEventsConverter handles the conversion of Notifications
    from openstack systems into Ceilometer Events.

    The conversion is handled according to event definitions in a config file.

    The config is a list of event definitions. Order is significant, a
    notification will be processed according to the LAST definition that
    matches it's event_type. (We use the last matching definition because that
    allows you to use YAML merge syntax in the definitions file.)
    Each definition is a dictionary with the following keys (all are
    required):

    - event_type: this is a list of notification event_types this definition
      will handle. These can be wildcarded with unix shell glob (not regex!)
      wildcards.
      An exclusion listing (starting with a '!') will exclude any types listed
      from matching. If ONLY exclusions are listed, the definition will match
      anything not matching the exclusions.
      This item can also be a string, which will be taken as equivalent to 1
      item list.

                Examples:

                * ['compute.instance.exists'] will only match
                  compute.instance.exists notifications
                * "compute.instance.exists"   Same as above.
                * ["image.create", "image.delete"]  will match
                  image.create and image.delete, but not anything else.
                * "compute.instance.*" will match
                  compute.instance.create.start but not image.upload
                * ['*.start','*.end', '!scheduler.*'] will match
                  compute.instance.create.start, and image.delete.end,
                  but NOT compute.instance.exists or
                  scheduler.run_instance.start
                * '!image.*' matches any notification except image
                  notifications.
                * ['*', '!image.*']  same as above.

    - traits: (dict) The keys are trait names, the values are the trait
      definitions. Each trait definition is a dictionary with the following
      keys:

      - type (optional): The data type for this trait. (as a string)
        Valid options are: 'text', 'int', 'float' and 'datetime', defaults to
        'text' if not specified.
      - fields:  a path specification for the field(s) in the notification you
        wish to extract. The paths can be specified with a dot syntax
        (e.g. 'payload.host') or dictionary syntax (e.g. 'payload[host]') is
        also supported.
        In either case, if the key for the field you are looking for contains
        special characters, like '.', it will need to be quoted (with double
        or single quotes) like so::

         "payload.image_meta.'org.openstack__1__architecture'"

        The syntax used for the field specification is a variant of JSONPath,
        and is fairly flexible.
        (see: https://github.com/kennknowles/python-jsonpath-rw for more info)
        Specifications can be written to match multiple possible fields, the
        value for the trait will be derived from the matching fields that
        exist and have a non-null (i.e. is not None) values in the
        notification.
        By default the value will be the first such field. (plugins can alter
        that, if they wish)

        This configuration value is normally a string, for convenience, it can
        be specified as a list of specifications, which will be OR'ed together
        (a union query in jsonpath terms)
    - plugin (optional): (dictionary) with the following keys:

      - name: (string) name of a plugin to load
      - parameters: (optional) Dictionary of keyword args to pass
        to the plugin on initialization. See documentation on each plugin to
        see what arguments it accepts.

      For convenience, this value can also be specified as a string, which is
      interpreted as a plugin name, which will be loaded with no parameters.

    """

    def __init__(self, conf, events_config, trait_plugin_mgr):
        self.conf = conf

        raw_levels = [level.lower() for level in self.conf.event.store_raw]
        self.definitions = [
            EventDefinition(event_def, trait_plugin_mgr, raw_levels)
            for event_def in reversed(events_config)]

        add_catchall = not self.conf.event.drop_unmatched_notifications
        if add_catchall and not any(d.is_catchall for d in self.definitions):
            event_def = dict(event_type='*', traits={})
            self.definitions.append(EventDefinition(event_def,
                                                    trait_plugin_mgr,
                                                    raw_levels))

    def to_event(self, priority, notification_body):
        event_type = notification_body['event_type']
        message_id = notification_body['metadata']['message_id']
        edef = None
        for d in self.definitions:
            if d.match_type(event_type):
                edef = d
                break

        if edef is None:
            msg = (_('Dropping Notification %(type)s (uuid:%(msgid)s)')
                   % dict(type=event_type, msgid=message_id))
            if self.conf.event.drop_unmatched_notifications:
                LOG.debug(msg)
            else:
                # If drop_unmatched_notifications is False, this should
                # never happen. (mdragon)
                LOG.error(msg)
            return None

        return edef.to_event(priority, notification_body)


def setup_events(conf, trait_plugin_mgr):
    """Setup the event definitions from yaml config file."""
    return NotificationEventsConverter(
        conf,
        declarative.load_definitions(
            conf, [], conf.event.definitions_cfg_file,
            pkg_resources.resource_filename(
                'ceilometer', "pipeline/data/event_definitions.yaml")),
        trait_plugin_mgr)
