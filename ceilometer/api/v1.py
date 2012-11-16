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

# [ ] / -- information about this version of the API
#
# [ ] /extensions -- list of available extensions
# [ ] /extensions/<extension> -- details about a specific extension
#
# [ ] /sources -- list of known sources (where do we get this?)
# [ ] /sources/components -- list of components which provide metering
#                            data (where do we get this)?
#
# [x] /projects/<project>/resources -- list of resource ids
# [x] /resources -- list of resource ids
# [x] /sources/<source>/resources -- list of resource ids
# [x] /users/<user>/resources -- list of resource ids
#
# [x] /users -- list of user ids
# [x] /sources/<source>/users -- list of user ids
#
# [x] /projects -- list of project ids
# [x] /sources/<source>/projects -- list of project ids
#
# [ ] /resources/<resource> -- metadata
#
# [ ] /projects/<project>/meters -- list of meters reporting for parent obj
# [ ] /resources/<resource>/meters -- list of meters reporting for parent obj
# [ ] /sources/<source>/meters -- list of meters reporting for parent obj
# [ ] /users/<user>/meters -- list of meters reporting for parent obj
#
# [x] /projects/<project>/meters/<meter> -- events
# [x] /resources/<resource>/meters/<meter> -- events
# [x] /sources/<source>/meters/<meter> -- events
# [x] /users/<user>/meters/<meter> -- events
#
# [ ] /projects/<project>/meters/<meter>/duration -- total time for selected
#                                                    meter
# [x] /resources/<resource>/meters/<meter>/duration -- total time for selected
#                                                      meter
# [ ] /sources/<source>/meters/<meter>/duration -- total time for selected
#                                                  meter
# [ ] /users/<user>/meters/<meter>/duration -- total time for selected meter
#
# [ ] /projects/<project>/meters/<meter>/volume -- total or max volume for
#                                                  selected meter
# [x] /projects/<project>/meters/<meter>/volume/max -- max volume for
#                                                      selected meter
# [x] /projects/<project>/meters/<meter>/volume/sum -- total volume for
#                                                      selected meter
# [ ] /resources/<resource>/meters/<meter>/volume -- total or max volume for
#                                                    selected meter
# [x] /resources/<resource>/meters/<meter>/volume/max -- max volume for
#                                                        selected meter
# [x] /resources/<resource>/meters/<meter>/volume/sum -- total volume for
#                                                        selected meter
# [ ] /sources/<source>/meters/<meter>/volume -- total or max volume for
#                                                selected meter
# [ ] /users/<user>/meters/<meter>/volume -- total or max volume for selected
#                                            meter

import datetime

import flask

from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils

from ceilometer import storage


LOG = log.getLogger(__name__)


blueprint = flask.Blueprint('v1', __name__)


def request_wants_html():
    best = flask.request.accept_mimetypes \
        .best_match(['application/json', 'text/html'])
    return best == 'text/html' and \
        flask.request.accept_mimetypes[best] > \
        flask.request.accept_mimetypes['application/json']


## APIs for working with resources.

def _list_resources(source=None, user=None, project=None):
    """Return a list of resource identifiers.
    """
    q_ts = _get_query_timestamps(flask.request.args)
    resources = flask.request.storage_conn.get_resources(
        source=source,
        user=user,
        project=project,
        start_timestamp=q_ts['start_timestamp'],
        end_timestamp=q_ts['end_timestamp'],
        )
    return flask.jsonify(resources=list(resources))


@blueprint.route('/projects/<project>/resources')
def list_resources_by_project(project):
    """Return a list of resources owned by the project.

    :param project: The ID of the owning project.
    :param start_timestamp: Limits resources by last update time >= this value.
        (optional)
    :type start_timestamp: ISO date in UTC
    :param end_timestamp: Limits resources by last update time < this value.
        (optional)
    :type end_timestamp: ISO date in UTC
    """
    return _list_resources(project=project)


@blueprint.route('/resources')
def list_all_resources():
    """Return a list of all known resources.

    :param start_timestamp: Limits resources by last update time >= this value.
        (optional)
    :type start_timestamp: ISO date in UTC
    :param end_timestamp: Limits resources by last update time < this value.
        (optional)
    :type end_timestamp: ISO date in UTC
    """
    return _list_resources()


@blueprint.route('/sources/<source>')
def get_source(source):
    """Return a source details.

    :param source: The ID of the reporting source.
    """
    return flask.jsonify(flask.request.sources.get(source, {}))


@blueprint.route('/sources/<source>/resources')
def list_resources_by_source(source):
    """Return a list of resources for which a source is reporting
    data.

    :param source: The ID of the reporting source.
    :param start_timestamp: Limits resources by last update time >= this value.
        (optional)
    :type start_timestamp: ISO date in UTC
    :param end_timestamp: Limits resources by last update time < this value.
        (optional)
    :type end_timestamp: ISO date in UTC
    """
    return _list_resources(source=source)


@blueprint.route('/users/<user>/resources')
def list_resources_by_user(user):
    """Return a list of resources owned by the user.

    :param user: The ID of the owning user.
    :param start_timestamp: Limits resources by last update time >= this value.
        (optional)
    :type start_timestamp: ISO date in UTC
    :param end_timestamp: Limits resources by last update time < this value.
        (optional)
    :type end_timestamp: ISO date in UTC
    """
    return _list_resources(user=user)


## APIs for working with users.


def _list_users(source=None):
    """Return a list of user names.
    """
    users = flask.request.storage_conn.get_users(source=source)
    return flask.jsonify(users=list(users))


@blueprint.route('/users')
def list_all_users():
    """Return a list of all known user names.
    """
    return _list_users()


@blueprint.route('/sources/<source>/users')
def list_users_by_source(source):
    """Return a list of the users for which the source is reporting
    data.

    :param source: The ID of the source.
    """
    return _list_users(source=source)


## APIs for working with projects.


def _list_projects(source=None):
    """Return a list of project names.
    """
    projects = flask.request.storage_conn.get_projects(source=source)
    return flask.jsonify(projects=list(projects))


@blueprint.route('/projects')
def list_all_projects():
    """Return a list of all known project names.
    """
    return _list_projects()


@blueprint.route('/sources/<source>/projects')
def list_projects_by_source(source):
    """Return a list project names for which the source is reporting
    data.

    :param source: The ID of the source.
    """
    return _list_projects(source=source)


## APIs for working with events.


def _list_events(meter,
                 project=None,
                 resource=None,
                 source=None,
                 user=None):
    """Return a list of raw metering events.
    """
    f = storage.EventFilter(user=user,
                            project=project,
                            source=source,
                            meter=meter,
                            resource=resource,
                            )
    events = list(flask.request.storage_conn.get_raw_events(f))
    jsonified = flask.jsonify(events=events)
    if request_wants_html():
        return flask.templating.render_template('list_event.html',
                                                user=user,
                                                project=project,
                                                source=source,
                                                meter=meter,
                                                resource=resource,
                                                events=jsonified)
    return jsonified


@blueprint.route('/projects/<project>/meters/<meter>')
def list_events_by_project(project, meter):
    """Return a list of raw metering events for the project.

    :param project: The ID of the project.
    :param meter: The name of the meter.
    :param start_timestamp: Limits events by timestamp >= this value.
        (optional)
    :type start_timestamp: ISO date in UTC
    :param end_timestamp: Limits events by timestamp < this value.
        (optional)
    :type end_timestamp: ISO date in UTC
    """
    return _list_events(project=project,
                        meter=meter,
                        )


@blueprint.route('/resources/<resource>/meters/<meter>')
def list_events_by_resource(resource, meter):
    """Return a list of raw metering events for the resource.

    :param resource: The ID of the resource.
    :param meter: The name of the meter.
    :param start_timestamp: Limits events by timestamp >= this value.
        (optional)
    :type start_timestamp: ISO date in UTC
    :param end_timestamp: Limits events by timestamp < this value.
        (optional)
    :type end_timestamp: ISO date in UTC
    """
    return _list_events(resource=resource,
                        meter=meter,
                        )


@blueprint.route('/sources/<source>/meters/<meter>')
def list_events_by_source(source, meter):
    """Return a list of raw metering events for the source.

    :param source: The ID of the reporting source.
    :param meter: The name of the meter.
    :param start_timestamp: Limits events by timestamp >= this value.
        (optional)
    :type start_timestamp: ISO date in UTC
    :param end_timestamp: Limits events by timestamp < this value.
        (optional)
    :type end_timestamp: ISO date in UTC
    """
    return _list_events(source=source,
                        meter=meter,
                        )


@blueprint.route('/users/<user>/meters/<meter>')
def list_events_by_user(user, meter):
    """Return a list of raw metering events for the user.

    :param user: The ID of the user.
    :param meter: The name of the meter.
    :param start_timestamp: Limits events by timestamp >= this value.
        (optional)
    :type start_timestamp: ISO date in UTC
    :param end_timestamp: Limits events by timestamp < this value.
        (optional)
    :type end_timestamp: ISO date in UTC
    """
    return _list_events(user=user,
                        meter=meter,
                        )


## APIs for working with meter calculations.


def _get_query_timestamps(args={}):
    # Determine the desired range, if any, from the
    # GET arguments. Set up the query range using
    # the specified offset.
    # [query_start ... start_timestamp ... end_timestamp ... query_end]
    search_offset = int(args.get('search_offset', 0))

    start_timestamp = args.get('start_timestamp')
    if start_timestamp:
        start_timestamp = timeutils.parse_isotime(start_timestamp)
        start_timestamp = start_timestamp.replace(tzinfo=None)
        query_start = (start_timestamp -
                       datetime.timedelta(minutes=search_offset))
    else:
        query_start = None

    end_timestamp = args.get('end_timestamp')
    if end_timestamp:
        end_timestamp = timeutils.parse_isotime(end_timestamp)
        end_timestamp = end_timestamp.replace(tzinfo=None)
        query_end = end_timestamp + datetime.timedelta(minutes=search_offset)
    else:
        query_end = None

    return dict(query_start=query_start,
                query_end=query_end,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                search_offset=search_offset,
                )


@blueprint.route('/resources/<resource>/meters/<meter>/duration')
def compute_duration_by_resource(resource, meter):
    """Return the earliest timestamp, last timestamp,
    and duration for the resource and meter.

    :param resource: The ID of the resource.
    :param meter: The name of the meter.
    :param start_timestamp: ISO-formatted string of the
        earliest timestamp to return.
    :param end_timestamp: ISO-formatted string of the
        latest timestamp to return.
    :param search_offset: Number of minutes before
        and after start and end timestamps to query.
    """
    q_ts = _get_query_timestamps(flask.request.args)
    start_timestamp = q_ts['start_timestamp']
    end_timestamp = q_ts['end_timestamp']

    # Query the database for the interval of timestamps
    # within the desired range.
    f = storage.EventFilter(meter=meter,
                            resource=resource,
                            start=q_ts['query_start'],
                            end=q_ts['query_end'],
                            )
    min_ts, max_ts = flask.request.storage_conn.get_event_interval(f)

    # "Clamp" the timestamps we return to the original time
    # range, excluding the offset.
    LOG.debug('start_timestamp %s, end_timestamp %s, min_ts %s, max_ts %s',
              start_timestamp, end_timestamp, min_ts, max_ts)
    if start_timestamp and min_ts and min_ts < start_timestamp:
        min_ts = start_timestamp
        LOG.debug('clamping min timestamp to range')
    if end_timestamp and max_ts and max_ts > end_timestamp:
        max_ts = end_timestamp
        LOG.debug('clamping max timestamp to range')

    # If we got valid timestamps back, compute a duration in minutes.
    #
    # If the min > max after clamping then we know the
    # timestamps on the events fell outside of the time
    # range we care about for the query, so treat them as
    # "invalid."
    #
    # If the timestamps are invalid, return None as a
    # sentinal indicating that there is something "funny"
    # about the range.
    if min_ts and max_ts and (min_ts <= max_ts):
        # Can't use timedelta.total_seconds() because
        # it is not available in Python 2.6.
        diff = max_ts - min_ts
        duration = (diff.seconds + (diff.days * 24 * 60 ** 2)) / 60
    else:
        min_ts = max_ts = duration = None

    return flask.jsonify(start_timestamp=min_ts,
                         end_timestamp=max_ts,
                         duration=duration,
                         )


@blueprint.route('/resources/<resource>/meters/<meter>/volume/max')
def compute_max_resource_volume(resource, meter):
    """Return the max volume for a meter.

    :param resource: The ID of the resource.
    :param meter: The name of the meter.
    :param start_timestamp: ISO-formatted string of the
        earliest time to include in the calculation.
    :param end_timestamp: ISO-formatted string of the
        latest time to include in the calculation.
    :param search_offset: Number of minutes before and
        after start and end timestamps to query.
    """
    q_ts = _get_query_timestamps(flask.request.args)

    # Query the database for the max volume
    f = storage.EventFilter(meter=meter,
                            resource=resource,
                            start=q_ts['query_start'],
                            end=q_ts['query_end'],
                            )
    # TODO(sberler): do we want to return an error if the resource
    # does not exist?
    results = list(flask.request.storage_conn.get_volume_max(f))
    value = None
    if results:
        value = results[0].get('value')  # there should only be one!

    return flask.jsonify(volume=value)


@blueprint.route('/resources/<resource>/meters/<meter>/volume/sum')
def compute_resource_volume_sum(resource, meter):
    """Return the total volume for a meter.

    :param resource: The ID of the resource.
    :param meter: The name of the meter.
    :param start_timestamp: ISO-formatted string of the
        earliest time to include in the calculation.
    :param end_timestamp: ISO-formatted string of the
        latest time to include in the calculation.
    :param search_offset: Number of minutes before and
        after start and end timestamps to query.
    """
    q_ts = _get_query_timestamps(flask.request.args)

    # Query the database for the max volume
    f = storage.EventFilter(meter=meter,
                            resource=resource,
                            start=q_ts['query_start'],
                            end=q_ts['query_end'],
                            )
    # TODO(sberler): do we want to return an error if the resource
    # does not exist?
    results = list(flask.request.storage_conn.get_volume_sum(f))
    value = None
    if results:
        value = results[0].get('value')  # there should only be one!

    return flask.jsonify(volume=value)


@blueprint.route('/projects/<project>/meters/<meter>/volume/max')
def compute_project_volume_max(project, meter):
    """Return the max volume for a meter.

    :param project: The ID of the project.
    :param meter: The name of the meter.
    :param start_timestamp: ISO-formatted string of the
        earliest time to include in the calculation.
    :param end_timestamp: ISO-formatted string of the
        latest time to include in the calculation.
    :param search_offset: Number of minutes before and
        after start and end timestamps to query.
    """
    q_ts = _get_query_timestamps(flask.request.args)

    f = storage.EventFilter(meter=meter,
                            project=project,
                            start=q_ts['query_start'],
                            end=q_ts['query_end'],
                            )
    # FIXME(sberler): Currently get_volume_max is really always grouping
    # by resource_id.  We should add a new function in the storage driver
    # that does not do this grouping (and potentially rename the existing
    # one to get_volume_max_by_resource())
    results = list(flask.request.storage_conn.get_volume_max(f))
    value = None
    if results:
        value = max(result.get('value') for result in results)

    return flask.jsonify(volume=value)


@blueprint.route('/projects/<project>/meters/<meter>/volume/sum')
def compute_project_volume_sum(project, meter):
    """Return the total volume for a meter.

    :param project: The ID of the project.
    :param meter: The name of the meter.
    :param start_timestamp: ISO-formatted string of the
        earliest time to include in the calculation.
    :param end_timestamp: ISO-formatted string of the
        latest time to include in the calculation.
    :param search_offset: Number of minutes before and
        after start and end timestamps to query.
    """
    q_ts = _get_query_timestamps(flask.request.args)

    f = storage.EventFilter(meter=meter,
                            project=project,
                            start=q_ts['query_start'],
                            end=q_ts['query_end'],
                            )
    # FIXME(sberler): Currently get_volume_max is really always grouping
    # by resource_id.  We should add a new function in the storage driver
    # that does not do this grouping (and potentially rename the existing
    # one to get_volume_max_by_resource())
    results = list(flask.request.storage_conn.get_volume_sum(f))
    value = None
    if results:
        value = sum(result.get('value') for result in results)

    return flask.jsonify(volume=value)
