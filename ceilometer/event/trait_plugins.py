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

import abc

from oslo_log import log
from oslo_utils import timeutils

LOG = log.getLogger(__name__)


class TraitPluginBase(metaclass=abc.ABCMeta):
    """Base class for plugins.

    It converts notification fields to Trait values.
    """

    support_return_all_values = False
    """If True, an exception will be raised if the user expect
    the plugin to return one trait per match_list, but
    the plugin doesn't allow/support that.
    """

    def __init__(self, **kw):
        """Setup the trait plugin.

        For each Trait definition a plugin is used on in a conversion
        definition, a new instance of the plugin will be created, and
        initialized with the parameters (if any) specified in the
        config file.

        :param kw: the parameters specified in the event definitions file.

        """
        super().__init__()

    @abc.abstractmethod
    def trait_values(self, match_list):
        """Convert a set of fields to one or multiple Trait values.

        This method is called each time a trait is attempted to be extracted
        from a notification. It will be called *even if* no matching fields
        are found in the notification (in that case, the match_list will be
        empty). If this method returns None, the trait *will not* be added to
        the event. Any other value returned by this method will be used as
        the value for the trait. Values returned will be coerced to the
        appropriate type for the trait.

        :param match_list: A list (may be empty if no matches) of *tuples*.
          Each tuple is (field_path, value) where field_path is the jsonpath
          for that specific field.

        Example::

            trait's fields definition: ['payload.foobar',
                                        'payload.baz',
                                        'payload.thing.*']
            notification body:
                        {
                         'metadata': {'message_id': '12345'},
                         'publisher': 'someservice.host',
                         'payload': {
                                     'foobar': 'test',
                                     'thing': {
                                               'bar': 12,
                                               'boing': 13,
                                              }
                                    }
                        }
            match_list will be: [('payload.foobar','test'),
                                 ('payload.thing.bar',12),
                                 ('payload.thing.boing',13)]

        Here is a plugin that emulates the default (no plugin) behavior:

        .. code-block:: python

          class DefaultPlugin(TraitPluginBase):
              "Plugin that returns the first field value."

              def __init__(self, **kw):
                  super(DefaultPlugin, self).__init__()

              def trait_values(self, match_list):
                  if not match_list:
                      return None
                  return [ match[1] for match in match_list]
        """


class SplitterTraitPlugin(TraitPluginBase):
    """Plugin that splits a piece off of a string value."""

    support_return_all_values = True

    def __init__(self, separator=".", segment=0, max_split=None, **kw):
        """Setup how do split the field.

        :param  separator:  String to split on. default "."
        :param  segment:    Which segment to return. (int) default 0
        :param  max_split: Limit number of splits. Default: None (no limit)
        """
        LOG.warning('split plugin is deprecated, '
                    'add ".`split(%(sep)s, %(segment)d, '
                    '%(max_split)d)`" to your jsonpath instead' %
                    dict(sep=separator,
                         segment=segment,
                         max_split=(-1 if max_split is None
                                    else max_split)))

        self.separator = separator
        self.segment = segment
        self.max_split = max_split
        super().__init__(**kw)

    def trait_values(self, match_list):
        return [self._trait_value(match)
                for match in match_list]

    def _trait_value(self, match):
        value = str(match[1])
        if self.max_split is not None:
            values = value.split(self.separator, self.max_split)
        else:
            values = value.split(self.separator)
        try:
            return values[self.segment]
        except IndexError:
            return None


class BitfieldTraitPlugin(TraitPluginBase):
    """Plugin to set flags on a bitfield."""
    def __init__(self, initial_bitfield=0, flags=None, **kw):
        """Setup bitfield trait.

        :param initial_bitfield: (int) initial value for the bitfield
                                 Flags that are set will be OR'ed with this.
        :param flags: List of dictionaries defining bitflags to set depending
                      on data in the notification. Each one has the following
                      keys:
                            path: jsonpath of field to match.
                            bit: (int) number of bit to set (lsb is bit 0)
                            value: set bit if corresponding field's value
                                   matches this. If value is not provided,
                                   bit will be set if the field exists (and
                                   is non-null), regardless of its value.

        """
        self.initial_bitfield = initial_bitfield
        if flags is None:
            flags = []
        self.flags = flags
        super().__init__(**kw)

    def trait_values(self, match_list):
        matches = dict(match_list)
        bitfield = self.initial_bitfield
        for flagdef in self.flags:
            path = flagdef['path']
            bit = 2 ** int(flagdef['bit'])
            if path in matches:
                if 'value' in flagdef:
                    if matches[path] == flagdef['value']:
                        bitfield |= bit
                else:
                    bitfield |= bit
        return [bitfield]


class TimedeltaPluginMissedFields(Exception):
    def __init__(self):
        msg = ('It is required to use two timestamp field with Timedelta '
               'plugin.')
        super().__init__(msg)


class TimedeltaPlugin(TraitPluginBase):
    """Setup timedelta meter volume of two timestamps fields.

    Example::

        trait's fields definition: ['payload.created_at',
                                    'payload.launched_at']
        value is been created as total seconds between 'launched_at' and
        'created_at' timestamps.
    """
    # TODO(idegtiarov): refactor code to have meter_plugins separate from
    # trait_plugins

    def trait_values(self, match_list):
        if len(match_list) != 2:
            LOG.warning('Timedelta plugin is required two timestamp fields'
                        ' to create timedelta value.')
            return [None]
        start, end = match_list
        try:
            start_time = timeutils.parse_isotime(start[1])
            end_time = timeutils.parse_isotime(end[1])
        except Exception as err:
            LOG.warning('Failed to parse date from set fields, both '
                        'fields %(start)s and %(end)s must be datetime: '
                        '%(err)s' %
                        dict(start=start[0], end=end[0], err=err)
                        )
            return [None]
        return [abs((end_time - start_time).total_seconds())]


class MapTraitPlugin(TraitPluginBase):
    """A trait plugin for mapping one set of values to another."""

    def __init__(self, values=None, default=None, case_sensitive=True, **kw):
        """Setup map trait.

        :param values: (dict[Any, Any]) Mapping of values to their
                       desired target values.
        :param default: (Any) Value to set if no mapping for a value is found.
        :param case_sensitive: (bool) Perform case-sensitive string lookups.
        """
        if not values:
            raise ValueError("The 'values' parameter is required "
                             "for the map trait plugin")
        if not isinstance(values, dict):
            raise ValueError("The 'values' parameter needs to be a dict "
                             "for the map trait plugin")
        self.case_sensitive = case_sensitive
        if not self.case_sensitive:
            self.values = {(k.casefold()
                            if isinstance(k, str)
                            else k): v
                           for k, v in values.items()}
        else:
            self.values = dict(values)
        self.default = default
        super().__init__(**kw)

    def trait_values(self, match_list):
        mapped_values = []
        for match in match_list:
            key = match[1]
            folded_key = (
                key.casefold()
                if not self.case_sensitive and isinstance(key, str)
                else key)
            try:
                value = self.values[folded_key]
            except KeyError:
                LOG.warning(
                    ('Unknown value %s found when mapping %s, '
                     'mapping to default value of %s'),
                    repr(key),
                    match[0],
                    repr(self.default))
                value = self.default
            else:
                LOG.debug('Value %s for %s mapped to value %s',
                          repr(key),
                          match[0],
                          repr(value))
            mapped_values.append(value)
        return mapped_values
