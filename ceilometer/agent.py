#
# Copyright 2013 Intel Corp.
# Copyright 2014 Red Hat, Inc
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
import pkg_resources

from oslo_log import log
from oslo_utils import fnmatch
import yaml

LOG = log.getLogger(__name__)


class ConfigException(Exception):
    def __init__(self, cfg_type, message, cfg):
        self.cfg_type = cfg_type
        self.msg = message
        self.cfg = cfg

    def __str__(self):
        return '%s %s: %s' % (self.cfg_type, self.cfg, self.msg)


class SourceException(Exception):
    def __init__(self, message, cfg):
        self.msg = message
        self.cfg = cfg

    def __str__(self):
        return 'Source definition invalid: %s (%s)' % (self.msg, self.cfg)


class ConfigManagerBase(object):
    """Base class for managing configuration file refresh"""

    def __init__(self, conf):
        self.conf = conf

    def load_config(self, cfg_file):
        """Load a configuration file and set its refresh values."""
        if os.path.exists(cfg_file):
            cfg_loc = cfg_file
        else:
            cfg_loc = self.conf.find_file(cfg_file)
            if not cfg_loc:
                LOG.debug("No pipeline definitions configuration file found! "
                          "Using default config.")
                cfg_loc = pkg_resources.resource_filename(
                    __name__, 'pipeline/data/' + cfg_file)
        with open(cfg_loc) as fap:
            conf = yaml.safe_load(fap)
        LOG.debug("Config file: %s", conf)
        return conf


class Source(object):
    """Represents a generic source"""

    def __init__(self, cfg):
        self.cfg = cfg
        try:
            self.name = cfg['name']
        except KeyError as err:
            raise SourceException(
                "Required field %s not specified" % err.args[0], cfg)

    def __str__(self):
        return self.name

    def check_source_filtering(self, data, d_type):
        """Source data rules checking

        - At least one meaningful datapoint exist
        - Included type and excluded type can't co-exist on the same pipeline
        - Included type meter and wildcard can't co-exist at same pipeline
        """
        if not data:
            raise SourceException('No %s specified' % d_type, self.cfg)

        if (any(x for x in data if x[0] not in '!*') and
           any(x for x in data if x[0] == '!')):
            raise SourceException(
                'Both included and excluded %s specified' % d_type,
                self.cfg)

        if '*' in data and any(x for x in data if x[0] not in '!*'):
            raise SourceException(
                'Included %s specified with wildcard' % d_type,
                self.cfg)

    @staticmethod
    def is_supported(dataset, data_name):
        # Support wildcard like storage.* and !disk.*
        # Start with negation, we consider that the order is deny, allow
        if any(fnmatch.fnmatch(data_name, datapoint[1:])
               for datapoint in dataset if datapoint[0] == '!'):
            return False

        if any(fnmatch.fnmatch(data_name, datapoint)
               for datapoint in dataset if datapoint[0] != '!'):
            return True

        # if we only have negation, we suppose the default is allow
        return all(datapoint.startswith('!') for datapoint in dataset)
