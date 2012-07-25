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
"""Blueprint for version 1 of API.
"""

import flask


blueprint = flask.Blueprint('v1', __name__)

## APIs for working with resources.


@blueprint.route('/resources', defaults={'source': None})
@blueprint.route('/sources/<source>/resources')
def list_resources(source):
    resources = list(flask.request.storage_conn.get_resources(source=source))
    return flask.jsonify(resources=resources)

## APIs for working with users.


@blueprint.route('/users', defaults={'source': None})
@blueprint.route('/sources/<source>/users')
def list_users(source):
    users = list(flask.request.storage_conn.get_users(source=source))
    return flask.jsonify(users=users)
