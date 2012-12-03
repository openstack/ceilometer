# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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

from pecan import make_app
from ceilometer.api import hooks
from ceilometer.api import middleware
from ceilometer.service import prepare_service


def setup_app(config, extra_hooks=[]):

    # Initialize the cfg.CONF object
    prepare_service([])

    # FIXME: Replace DBHook with a hooks.TransactionHook
    app_hooks = [hooks.ConfigHook(),
                 hooks.DBHook()]
    app_hooks.extend(extra_hooks)

    return make_app(
        config.app.root,
        static_root=config.app.static_root,
        template_path=config.app.template_path,
        logging=getattr(config, 'logging', {}),
        debug=getattr(config.app, 'debug', False),
        force_canonical=getattr(config.app, 'force_canonical', True),
        hooks=app_hooks,
        wrap_app=middleware.ParsableErrorMiddleware,
    )
