# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Rackspace Hosting.
#
# Author: Monsyne Dragon <mdragon@rackspace.com>
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
import six


@six.add_metaclass(abc.ABCMeta)
class TraitPluginBase(object):
    """Base class for plugins that convert notification fields to
       Trait values.
    """

    def __init__(self, **kw):
        """Setup the trait plugin.

        For each Trait definition a plugin is used on in a conversion
        definition, a new instance of the plugin will be created, and
        initialized with the parameters (if any) specified in the
        config file.

        :param kw: the parameters specified in the event definitions file.

        """
        super(TraitPluginBase, self).__init__()

    @abc.abstractmethod
    def trait_value(self, match_list):
        """Convert a set of fields to a Trait value.

        This method is called each time a trait is attempted to be extracted
        from a notification. It will be called *even if* no matching fields
        are found in the notification (in that case, the match_list will be
        empty). If this method returns None, the trait *will not* be added to
        the event. Any other value returned by this method will be used as
        the value for the trait. Values returned will be coerced to the
        appropriate type for the trait.

        :param match_list: A list (may be empty if no matches) of *tuples*.
                          Each tuple is (field_path, value) where field_path
                          is the jsonpath for that specific field,

        Example:
            trait's fields definition: ['payload.foobar',
                                        'payload.baz',
                                        'payload.thing.*']
            notification body:
                        {
                            'message_id': '12345',
                            'publisher':    'someservice.host',
                            'payload':  {
                                            'foobar': 'test',
                                            'thing':    {
                                                            'bar': 12,
                                                            'boing': 13,
                                                        }
                                        }
                        }
            match_list will be: [('payload.foobar','test'),
                                 ('payload.thing.bar',12),
                                 ('payload.thing.boing',13)]

        Here is a plugin that emulates the default (no plugin) behavior:

        class DefaultPlugin(TraitPluginBase):
            "Plugin that returns the first field value"

            def __init__(self, **kw):
                super(DefaultPlugin, self).__init__()

            def trait_value(self, match_list):
                if not match_list:
                    return None
                return match_list[0][1]
        """


class SplitterTraitPlugin(TraitPluginBase):
    """Plugin that splits a piece off of a string value."""

    def __init__(self, separator=".", segment=0, max_split=None, **kw):
        """Setup how do split the field.

        :param  separator:  String to split on. default "."
        :param  segment:    Which segment to return. (int) default 0
        :param  max_split: Limit number of splits. Default: None (no limit)
        """
        self.separator = separator
        self.segment = segment
        self.max_split = max_split
        super(SplitterTraitPlugin, self).__init__(**kw)

    def trait_value(self, match_list):
        if not match_list:
            return None
        value = str(match_list[0][1])
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
                            value: set bit if corrosponding field's value
                                   matches this. If value is not provided,
                                   bit will be set if the field exists (and
                                   is non-null), regardless of it's value.

        """
        self.initial_bitfield = initial_bitfield
        if flags is None:
            flags = []
        self.flags = flags
        super(BitfieldTraitPlugin, self).__init__(**kw)

    def trait_value(self, match_list):
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
        return bitfield
