# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
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
"""Set up the ACL to acces the API server."""

import flask
from ceilometer.openstack.common import cfg
from ceilometer import policy

import keystone.middleware.auth_token

# Register keystone middleware option
cfg.CONF.register_opts(keystone.middleware.auth_token.opts,
                       group='keystone_authtoken')
keystone.middleware.auth_token.CONF = cfg.CONF


def install(app):
    """Install ACL check on application."""
    app.wsgi_app = keystone.middleware.auth_token.AuthProtocol(app.wsgi_app,
                                                               {})
    app.before_request(check)


def check():
    """Check application access."""
    headers = flask.request.headers
    if not policy.check_is_admin(headers.get('X-Roles', "").split(","),
                                 headers.get('X-Tenant-Id'),
                                 headers.get('X-Tenant-Name')):
        return "Access denied", 401
