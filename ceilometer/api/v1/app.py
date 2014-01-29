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
"""Set up the API server application instance."""

import flask
from oslo.config import cfg

from ceilometer.api import acl
from ceilometer.api.v1 import blueprint as v1_blueprint
from ceilometer.openstack.common import jsonutils
from ceilometer import storage


class JSONEncoder(flask.json.JSONEncoder):
    @staticmethod
    def default(o):
        return jsonutils.to_primitive(o)


def make_app(conf, enable_acl=True, attach_storage=True,
             sources_file='sources.json'):
    app = flask.Flask('ceilometer.api')
    app.register_blueprint(v1_blueprint.blueprint, url_prefix='/v1')

    app.json_encoder = JSONEncoder

    try:
        with open(sources_file, "r") as f:
            sources = jsonutils.load(f)
    except IOError:
        sources = {}

    @app.before_request
    def attach_config():
        flask.request.cfg = conf
        flask.request.sources = sources

    if attach_storage:
        @app.before_request
        def attach_storage():
            flask.request.storage_conn = \
                storage.get_connection(conf)

    # Install the middleware wrapper
    if enable_acl:
        app.wsgi_app = acl.install(app.wsgi_app, conf)

    return app

# For documentation
app = make_app(cfg.CONF, enable_acl=False, attach_storage=False)
