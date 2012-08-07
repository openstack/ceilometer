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

from ceilometer.openstack.common import log
from ceilometer import storage


LOG = log.getLogger(__name__)


blueprint = flask.Blueprint('v1', __name__)


## APIs for working with resources.


@blueprint.route('/resources', defaults={'source': None})
@blueprint.route('/sources/<source>/resources')
@blueprint.route('/users/<user>/resources')
@blueprint.route('/projects/<project>/resources')
@blueprint.route('/sources/<source>/users/<user>/resources')
@blueprint.route('/sources/<source>/projects/<project>/resources')
def list_resources(source=None, user=None, project=None):
    """Return a list of resource names.
    """
    resources = flask.request.storage_conn.get_resources(
        source=source,
        user=user,
        project=project,
        )
    return flask.jsonify(resources=list(resources))


## APIs for working with users.


@blueprint.route('/users', defaults={'source': None})
@blueprint.route('/sources/<source>/users')
def list_users(source):
    """Return a list of user names.
    """
    users = flask.request.storage_conn.get_users(source=source)
    return flask.jsonify(users=list(users))


## APIs for working with projects.


@blueprint.route('/projects', defaults={'source': None})
@blueprint.route('/sources/<source>/projects')
def list_projects(source):
    """Return a list of project names.
    """
    projects = flask.request.storage_conn.get_projects(source=source)
    return flask.jsonify(projects=list(projects))


## APIs for working with events.


@blueprint.route('/projects/<project>')
@blueprint.route('/projects/<project>/meters/<meter>')
@blueprint.route('/projects/<project>/resources/<resource>')
@blueprint.route('/projects/<project>/resources/<resource>/meters/<meter>')
@blueprint.route('/sources/<source>/projects/<project>')
@blueprint.route('/sources/<source>/projects/<project>/meters/<meter>')
@blueprint.route('/sources/<source>/projects/<project>/resources/<resource>')
@blueprint.route(
    '/sources/<source>/projects/<project>/resources/<resource>/meters/<meter>'
    )
@blueprint.route('/users/<user>')
@blueprint.route('/users/<user>/meters/<meter>')
@blueprint.route('/users/<user>/resources/<resource>')
@blueprint.route('/users/<user>/resources/<resource>/meters/<meter>')
@blueprint.route('/sources/<source>/users/<user>')
@blueprint.route('/sources/<source>/users/<user>/meters/<meter>')
@blueprint.route('/sources/<source>/users/<user>/resources/<resource>')
@blueprint.route(
    '/sources/<source>/users/<user>/resources/<resource>/meters/<meter>'
    )
def list_events(user=None,
                meter=None,
                resource=None,
                source=None,
                project=None,
                ):
    """Return a list of raw metering events.
    """
    f = storage.EventFilter(user=user,
                            project=project,
                            source=source,
                            meter=meter,
                            resource=resource,
                            )
    events = flask.request.storage_conn.get_raw_events(f)
    return flask.jsonify(events=list(events))
