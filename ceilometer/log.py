# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
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
import inspect
import logging
import logging.config
import traceback
import sys

from ceilometer.openstack.common import cfg

cfg.CONF.register_opts(
    [
        cfg.StrOpt('log_level',
                   default="debug",
                   help='Log level',
                   ),
        cfg.StrOpt('logging_default_format_string',
                   default='%(asctime)s %(levelname)s %(name)s: %(message)s',
                   help='format string to use for log messages'),
        ]
    )


def _get_binary_name():
    return os.path.basename(inspect.stack()[-1][1])


def _get_log_file_path(binary=None):
    if cfg.CONF.log_file and not cfg.CONF.log_dir:
        return cfg.CONF.log_file

    if cfg.CONF.log_file and cfg.CONF.log_dir:
        return os.path.join(cfg.CONF.log_file,
                            cfg.CONF.log_file)

    if cfg.CONF.log_dir:
        binary = binary or _get_binary_name()
        return '%s.log' % (os.path.join(cfg.CONF.log_dir, binary),)


def getLogger(name='ceilometer'):
    return logging.getLogger(name)


def _setup_default_logger(logger_name):
    """Configure a single logger."""
    root = getLogger(logger_name)
    for handler in root.handlers:
        root.removeHandler(handler)
    logpath = _get_log_file_path()
    if logpath:
        filelog = logging.handlers.WatchedFileHandler(logpath)
        filelog.setFormatter(
            logging.Formatter(cfg.CONF.logging_default_format_string))
        root.addHandler(filelog)

        mode = int(FLAGS.logfile_mode, 8)
        st = os.stat(logpath)
        if st.st_mode != (stat.S_IFREG | mode):
            os.chmod(logpath, mode)
    else:
        streamlog = logging.StreamHandler(sys.stdout)
        streamlog.setFormatter(
            logging.Formatter(cfg.CONF.logging_default_format_string))
        root.addHandler(streamlog)

    if cfg.CONF.log_level:
        root.setLevel(logging.getLevelName(cfg.CONF.log_level.upper()))


def setup():
    if cfg.CONF.log_config:
        try:
            logging.config.fileConfig(cfg.CONF.log_config)
        except Exception:
            traceback.print_exc()
            raise
    else:
        # Strip any existing log handlers to avoid seeing duplicate
        # messages on the console.
        root = getLogger(None)
        for handler in root.handlers:
            root.removeHandler(handler)
        _setup_default_logger('ceilometer')
        _setup_default_logger('nova')
