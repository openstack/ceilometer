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

from jsonpath_rw_ext import parser
from oslo_log import log
import six
import yaml

from ceilometer.i18n import _

LOG = log.getLogger(__name__)


class DefinitionException(Exception):
    def __init__(self, message, definition_cfg):
        msg = '%s %s: %s' % (self.__class__.__name__, definition_cfg, message)
        super(DefinitionException, self).__init__(msg)
        self.brief_message = message


class MeterDefinitionException(DefinitionException):
    pass


class EventDefinitionException(DefinitionException):
    pass


class ResourceDefinitionException(DefinitionException):
    pass


class Definition(object):
    JSONPATH_RW_PARSER = parser.ExtentedJsonPathParser()
    GETTERS_CACHE = {}

    def __init__(self, name, cfg, plugin_manager):
        self.cfg = cfg
        self.name = name
        self.plugin = None
        if isinstance(cfg, dict):
            if 'fields' not in cfg:
                raise DefinitionException(
                    _("The field 'fields' is required for %s") % name,
                    self.cfg)

            if 'plugin' in cfg:
                plugin_cfg = cfg['plugin']
                if isinstance(plugin_cfg, six.string_types):
                    plugin_name = plugin_cfg
                    plugin_params = {}
                else:
                    try:
                        plugin_name = plugin_cfg['name']
                    except KeyError:
                        raise DefinitionException(
                            _('Plugin specified, but no plugin name supplied '
                              'for %s') % name, self.cfg)
                    plugin_params = plugin_cfg.get('parameters')
                    if plugin_params is None:
                        plugin_params = {}
                try:
                    plugin_ext = plugin_manager[plugin_name]
                except KeyError:
                    raise DefinitionException(
                        _('No plugin named %(plugin)s available for '
                          '%(name)s') % dict(
                              plugin=plugin_name,
                              name=name), self.cfg)
                plugin_class = plugin_ext.plugin
                self.plugin = plugin_class(**plugin_params)

            fields = cfg['fields']
        else:
            # Simple definition "foobar: jsonpath"
            fields = cfg

        if isinstance(fields, list):
            # NOTE(mdragon): if not a string, we assume a list.
            if len(fields) == 1:
                fields = fields[0]
            else:
                fields = '|'.join('(%s)' % path for path in fields)

        if isinstance(fields, six.integer_types):
            self.getter = fields
        else:
            try:
                self.getter = self.make_getter(fields)
            except Exception as e:
                raise DefinitionException(
                    _("Parse error in JSONPath specification "
                      "'%(jsonpath)s' for %(name)s: %(err)s")
                    % dict(jsonpath=fields, name=name, err=e), self.cfg)

    def _get_path(self, match):
        if match.context is not None:
            for path_element in self._get_path(match.context):
                yield path_element
            yield str(match.path)

    def parse(self, obj, return_all_values=False):
        if callable(self.getter):
            values = self.getter(obj)
        else:
            return self.getter

        values = [match for match in values
                  if return_all_values or match.value is not None]

        if self.plugin is not None:
            if return_all_values and not self.plugin.support_return_all_values:
                raise DefinitionException("Plugin %s don't allows to "
                                          "return multiple values" %
                                          self.cfg["plugin"]["name"], self.cfg)
            values_map = [('.'.join(self._get_path(match)), match.value) for
                          match in values]
            values = [v for v in self.plugin.trait_values(values_map)
                      if v is not None]
        else:
            values = [match.value for match in values if match is not None]
        if return_all_values:
            return values
        else:
            return values[0] if values else None

    def make_getter(self, fields):
        if fields in self.GETTERS_CACHE:
            return self.GETTERS_CACHE[fields]
        else:
            getter = self.JSONPATH_RW_PARSER.parse(fields).find
            self.GETTERS_CACHE[fields] = getter
            return getter


def load_definitions(conf, defaults, config_file, fallback_file=None):
    """Setup a definitions from yaml config file."""

    if not os.path.exists(config_file):
        config_file = conf.find_file(config_file)
    if not config_file and fallback_file is not None:
        LOG.debug("No Definitions configuration file found! "
                  "Using default config.")
        config_file = fallback_file

    if config_file is not None:
        LOG.debug("Loading definitions configuration file: %s", config_file)

        with open(config_file) as cf:
            config = cf.read()

        try:
            definition_cfg = yaml.safe_load(config)
        except yaml.YAMLError as err:
            if hasattr(err, 'problem_mark'):
                mark = err.problem_mark
                errmsg = (_("Invalid YAML syntax in Definitions file "
                            "%(file)s at line: %(line)s, column: %(column)s.")
                          % dict(file=config_file,
                                 line=mark.line + 1,
                                 column=mark.column + 1))
            else:
                errmsg = (_("YAML error reading Definitions file "
                            "%(file)s")
                          % dict(file=config_file))
            LOG.error(errmsg)
            raise

    else:
        LOG.debug("No Definitions configuration file found! "
                  "Using default config.")
        definition_cfg = defaults

    LOG.info("Definitions: %s", definition_cfg)
    return definition_cfg
