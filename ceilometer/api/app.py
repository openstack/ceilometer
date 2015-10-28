#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

import logging
import os

from oslo_config import cfg
from oslo_log import log
from paste import deploy
import pecan
from werkzeug import serving

from ceilometer.api import hooks
from ceilometer.api import middleware
from ceilometer.i18n import _LI, _LW

LOG = log.getLogger(__name__)

CONF = cfg.CONF

OPTS = [
    cfg.StrOpt('api_paste_config',
               default="api_paste.ini",
               help="Configuration file for WSGI definition of API."
               ),
]

API_OPTS = [
    cfg.BoolOpt('pecan_debug',
                default=False,
                help='Toggle Pecan Debug Middleware.'),
    cfg.IntOpt('default_api_return_limit',
               min=1,
               default=100,
               help='Default maximum number of items returned by API request.'
               ),
]

CONF.register_opts(OPTS)
CONF.register_opts(API_OPTS, group='api')


def setup_app(pecan_config=None):
    # FIXME: Replace DBHook with a hooks.TransactionHook
    app_hooks = [hooks.ConfigHook(),
                 hooks.DBHook(),
                 hooks.NotifierHook(),
                 hooks.TranslationHook()]

    pecan_config = pecan_config or {
        "app": {
            'root': 'ceilometer.api.controllers.root.RootController',
            'modules': ['ceilometer.api'],
        }
    }

    pecan.configuration.set_config(dict(pecan_config), overwrite=True)

    # NOTE(sileht): pecan debug won't work in multi-process environment
    pecan_debug = CONF.api.pecan_debug
    if CONF.api.workers and CONF.api.workers != 1 and pecan_debug:
        pecan_debug = False
        LOG.warning(_LW('pecan_debug cannot be enabled, if workers is > 1, '
                        'the value is overrided with False'))

    app = pecan.make_app(
        pecan_config['app']['root'],
        debug=pecan_debug,
        hooks=app_hooks,
        wrap_app=middleware.ParsableErrorMiddleware,
        guess_content_type_from_ext=False
    )

    return app


def load_app():
    # Build the WSGI app
    cfg_file = None
    cfg_path = cfg.CONF.api_paste_config
    if not os.path.isabs(cfg_path):
        cfg_file = CONF.find_file(cfg_path)
    elif os.path.exists(cfg_path):
        cfg_file = cfg_path

    if not cfg_file:
        raise cfg.ConfigFilesNotFoundError([cfg.CONF.api_paste_config])
    LOG.info("Full WSGI config used: %s" % cfg_file)
    return deploy.loadapp("config:" + cfg_file)


def build_server():
    app = load_app()
    # Create the WSGI server and start it
    host, port = cfg.CONF.api.host, cfg.CONF.api.port

    LOG.info(_LI('Starting server in PID %s') % os.getpid())
    LOG.info(_LI("Configuration:"))
    cfg.CONF.log_opt_values(LOG, logging.INFO)

    if host == '0.0.0.0':
        LOG.info(_LI(
            'serving on 0.0.0.0:%(sport)s, view at http://127.0.0.1:%(vport)s')
            % ({'sport': port, 'vport': port}))
    else:
        LOG.info(_LI("serving on http://%(host)s:%(port)s") % (
                 {'host': host, 'port': port}))

    serving.run_simple(cfg.CONF.api.host, cfg.CONF.api.port,
                       app, processes=CONF.api.workers)


def app_factory(global_config, **local_conf):
    return setup_app()
