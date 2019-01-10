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
import hashlib
import os
import pkg_resources

from oslo_log import log
from oslo_utils import fnmatch
import six
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
        self.cfg_loc = None

    def load_config(self, cfg_file, fallback_cfg_prefix='pipeline/data/'):
        """Load a configuration file and set its refresh values."""
        if os.path.exists(cfg_file):
            self.cfg_loc = cfg_file
        else:
            self.cfg_loc = self.conf.find_file(cfg_file)
        if not self.cfg_loc and fallback_cfg_prefix is not None:
            LOG.debug("No pipeline definitions configuration file found! "
                      "Using default config.")
            self.cfg_loc = pkg_resources.resource_filename(
                __name__, fallback_cfg_prefix + cfg_file)
        with open(self.cfg_loc) as fap:
            data = fap.read()
        conf = yaml.safe_load(data)
        self.cfg_mtime = self.get_cfg_mtime()
        self.cfg_hash = self.get_cfg_hash()
        LOG.debug("Config file: %s", conf)
        return conf

    def get_cfg_mtime(self):
        """Return modification time of cfg file"""
        return os.path.getmtime(self.cfg_loc) if self.cfg_loc else None

    def get_cfg_hash(self):
        """Return hash of configuration file"""
        if not self.cfg_loc:
            return None

        with open(self.cfg_loc) as fap:
            data = fap.read()
        if six.PY3:
            data = data.encode('utf-8')

        file_hash = hashlib.md5(data).hexdigest()
        return file_hash

    def cfg_changed(self):
        """Returns hash of changed cfg else False."""
        mtime = self.get_cfg_mtime()
        if mtime > self.cfg_mtime:
            LOG.info('Configuration file has been updated.')
            self.cfg_mtime = mtime
            _hash = self.get_cfg_hash()
            if _hash != self.cfg_hash:
                LOG.info("Detected change in configuration.")
                return _hash
        return False


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

        if ([x for x in data if x[0] not in '!*'] and
           [x for x in data if x[0] == '!']):
            raise SourceException(
                'Both included and excluded %s specified' % d_type,
                self.cfg)

        if '*' in data and [x for x in data if x[0] not in '!*']:
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
