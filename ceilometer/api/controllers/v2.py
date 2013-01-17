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
"""Version 2 of the API.
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
import os

import pecan
from pecan import request
from pecan.rest import RestController

import wsme
import wsmeext.pecan as wsme_pecan
from wsme.types import Base, text, wsattr

from ceilometer.openstack.common import jsonutils
from ceilometer.openstack.common import log as logging
from ceilometer.openstack.common import timeutils
from ceilometer import storage


LOG = logging.getLogger(__name__)


# FIXME(dhellmann): Change APIs that use this to return float?
class MeterVolume(Base):
    volume = wsattr(float, mandatory=False)

    def __init__(self, volume, **kw):
        if volume is not None:
            volume = float(volume)
        super(MeterVolume, self).__init__(volume=volume, **kw)


class DateRange(Base):
    start = datetime.datetime
    end = datetime.datetime
    search_offset = int

    def __init__(self, start=None, end=None, search_offset=0):
        if start is not None:
            start = start.replace(tzinfo=None)
        if end is not None:
            end = end.replace(tzinfo=None)
        super(DateRange, self).__init__(start=start,
                                        end=end,
                                        search_offset=search_offset,
                                        )

    @property
    def query_start(self):
        """The timestamp the query should use to start, including
        the search offset.
        """
        if self.start is None:
            return None
        return (self.start -
                datetime.timedelta(minutes=self.search_offset))

    @property
    def query_end(self):
        """The timestamp the query should use to end, including
        the search offset.
        """
        if self.end is None:
            return None
        return (self.end +
                datetime.timedelta(minutes=self.search_offset))

    def to_dict(self):
        return {'query_start': self.query_start,
                'query_end': self.query_end,
                'start_timestamp': self.start,
                'end_timestamp': self.end,
                'search_offset': self.search_offset,
                }


class MeterVolumeController(object):

    @wsme_pecan.wsexpose(MeterVolume, DateRange)
    def max(self, daterange=None):
        """Find the maximum volume for the matching meter events.
        """
        if daterange is None:
            daterange = DateRange()
        q_ts = daterange.to_dict()

        try:
            meter = request.context['meter_id']
        except KeyError:
            raise ValueError('No meter specified')

        resource = request.context.get('resource_id')
        project = request.context.get('project_id')

        # Query the database for the max volume
        f = storage.EventFilter(meter=meter,
                                resource=resource,
                                start=q_ts['query_start'],
                                end=q_ts['query_end'],
                                project=project,
                                )

        # TODO(sberler): do we want to return an error if the resource
        # does not exist?
        results = list(request.storage_conn.get_volume_max(f))

        value = None
        if results:
            if resource:
                # If the caller specified a resource there should only
                # be one result.
                value = results[0].get('value')
            else:
                # FIXME(sberler): Currently get_volume_max is really
                # always grouping by resource_id.  We should add a new
                # function in the storage driver that does not do this
                # grouping (and potentially rename the existing one to
                # get_volume_max_by_resource())
                value = max(result.get('value') for result in results)

        return MeterVolume(volume=value)

    @wsme_pecan.wsexpose(MeterVolume, DateRange)
    def sum(self, daterange=None):
        """Compute the total volume for the matching meter events.
        """
        if daterange is None:
            daterange = DateRange()
        q_ts = daterange.to_dict()

        try:
            meter = request.context['meter_id']
        except KeyError:
            raise ValueError('No meter specified')

        resource = request.context.get('resource_id')
        project = request.context.get('project_id')

        f = storage.EventFilter(meter=meter,
                                project=project,
                                start=q_ts['query_start'],
                                end=q_ts['query_end'],
                                resource=resource,
                                )

        # TODO(sberler): do we want to return an error if the resource
        # does not exist?
        results = list(request.storage_conn.get_volume_sum(f))

        value = None
        if results:
            if resource:
                # If the caller specified a resource there should only
                # be one result.
                value = results[0].get('value')
            else:
                # FIXME(sberler): Currently get_volume_max is really
                # always grouping by resource_id.  We should add a new
                # function in the storage driver that does not do this
                # grouping (and potentially rename the existing one to
                # get_volume_max_by_resource())
                value = sum(result.get('value') for result in results)

        return MeterVolume(volume=value)


def _flatten_metadata(metadata):
    """Return flattened resource metadata without nested structures
    and with all values converted to unicode strings.
    """
    return dict((k, unicode(v))
                for k, v in metadata.iteritems()
                if type(v) not in set([list, dict, set]))


class Event(Base):
    source = text
    counter_name = text
    counter_type = text
    counter_unit = text
    counter_volume = float
    user_id = text
    project_id = text
    resource_id = text
    timestamp = datetime.datetime
    resource_metadata = {text: text}
    message_id = text

    def __init__(self, counter_volume=None, resource_metadata={}, **kwds):
        if counter_volume is not None:
            counter_volume = float(counter_volume)
        resource_metadata = _flatten_metadata(resource_metadata)
        super(Event, self).__init__(counter_volume=counter_volume,
                                    resource_metadata=resource_metadata,
                                    **kwds)


class Duration(Base):
    start_timestamp = datetime.datetime
    end_timestamp = datetime.datetime
    duration = float


class MeterController(RestController):
    """Manages operations on a single meter.
    """

    volume = MeterVolumeController()

    _custom_actions = {
        'duration': ['GET'],
    }

    def __init__(self, meter_id):
        request.context['meter_id'] = meter_id
        self._id = meter_id

    @wsme_pecan.wsexpose([Event], DateRange)
    def get_all(self, daterange=None):
        """Return all events for the meter.
        """
        if daterange is None:
            daterange = DateRange()
        f = storage.EventFilter(
            user=request.context.get('user_id'),
            project=request.context.get('project_id'),
            start=daterange.query_start,
            end=daterange.query_end,
            resource=request.context.get('resource_id'),
            meter=self._id,
            source=request.context.get('source_id'),
        )
        return [Event(**e)
                for e in request.storage_conn.get_raw_events(f)
                ]

    @wsme_pecan.wsexpose(Duration, DateRange)
    def duration(self, daterange=None):
        """Computes the duration of the meter events in the time range given.
        """
        if daterange is None:
            daterange = DateRange()

        # Query the database for the interval of timestamps
        # within the desired range.
        f = storage.EventFilter(user=request.context.get('user_id'),
                                project=request.context.get('project_id'),
                                start=daterange.query_start,
                                end=daterange.query_end,
                                resource=request.context.get('resource_id'),
                                meter=self._id,
                                source=request.context.get('source_id'),
                                )
        min_ts, max_ts = request.storage_conn.get_event_interval(f)

        # "Clamp" the timestamps we return to the original time
        # range, excluding the offset.
        LOG.debug('start_timestamp %s, end_timestamp %s, min_ts %s, max_ts %s',
                  daterange.start, daterange.end, min_ts, max_ts)
        if daterange.start and min_ts and min_ts < daterange.start:
            min_ts = daterange.start
            LOG.debug('clamping min timestamp to range')
        if daterange.end and max_ts and max_ts > daterange.end:
            max_ts = daterange.end
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

        return Duration(start_timestamp=min_ts,
                        end_timestamp=max_ts,
                        duration=duration,
                        )


class Meter(Base):
    name = text
    type = text
    resource_id = text
    project_id = text
    user_id = text


class MetersController(RestController):
    """Works on meters."""

    @pecan.expose()
    def _lookup(self, meter_id, *remainder):
        return MeterController(meter_id), remainder

    @wsme_pecan.wsexpose([Meter])
    def get_all(self):
        user_id = request.context.get('user_id')
        project_id = request.context.get('project_id')
        resource_id = request.context.get('resource_id')
        source_id = request.context.get('source_id')
        return [Meter(**m)
                for m in request.storage_conn.get_meters(user=user_id,
                                                         project=project_id,
                                                         resource=resource_id,
                                                         source=source_id,
                                                         )]


class ResourceController(RestController):
    """Manages operations on a single resource.
    """

    def __init__(self, resource_id):
        request.context['resource_id'] = resource_id

    meters = MetersController()


class MeterDescription(Base):
    counter_name = text
    counter_type = text


class Resource(Base):
    resource_id = text
    project_id = text
    user_id = text
    timestamp = datetime.datetime
    metadata = {text: text}
    meter = wsattr([MeterDescription])

    def __init__(self, meter=[], metadata={}, **kwds):
        meter = [MeterDescription(**m) for m in meter]
        metadata = _flatten_metadata(metadata)
        super(Resource, self).__init__(meter=meter,
                                       metadata=metadata,
                                       **kwds)


class ResourcesController(RestController):
    """Works on resources."""

    @pecan.expose()
    def _lookup(self, resource_id, *remainder):
        return ResourceController(resource_id), remainder

    @wsme_pecan.wsexpose([Resource])
    def get_all(self, start_timestamp=None, end_timestamp=None):
        if start_timestamp:
            start_timestamp = timeutils.parse_isotime(start_timestamp)
        if end_timestamp:
            end_timestamp = timeutils.parse_isotime(end_timestamp)

        resources = [
            Resource(**r)
            for r in request.storage_conn.get_resources(
                source=request.context.get('source_id'),
                user=request.context.get('user_id'),
                project=request.context.get('project_id'),
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
            )
        ]
        return resources


class ProjectController(RestController):
    """Works on resources."""

    def __init__(self, project_id):
        request.context['project_id'] = project_id

    meters = MetersController()
    resources = ResourcesController()


class ProjectsController(RestController):
    """Works on projects."""

    @pecan.expose()
    def _lookup(self, project_id, *remainder):
        return ProjectController(project_id), remainder

    @wsme_pecan.wsexpose([text])
    def get_all(self):
        source_id = request.context.get('source_id')
        projects = list(request.storage_conn.get_projects(source=source_id))
        return projects

    meters = MetersController()


class UserController(RestController):
    """Works on reusers."""

    def __init__(self, user_id):
        request.context['user_id'] = user_id

    meters = MetersController()
    resources = ResourcesController()


class UsersController(RestController):
    """Works on users."""

    @pecan.expose()
    def _lookup(self, user_id, *remainder):
        return UserController(user_id), remainder

    @wsme_pecan.wsexpose([text])
    def get_all(self):
        source_id = request.context.get('source_id')
        users = list(request.storage_conn.get_users(source=source_id))
        return users


class Source(Base):
    name = text
    data = {text: text}

    @staticmethod
    def sample():
        return Source(name='openstack',
                      data={'key': 'value'})


class SourceController(RestController):
    """Works on resources."""

    def __init__(self, source_id, data):
        request.context['source_id'] = source_id
        self._id = source_id
        self._data = data

    @wsme_pecan.wsexpose(Source)
    def get(self):
        response = Source(name=self._id, data=self._data)
        return response

    meters = MetersController()
    resources = ResourcesController()
    projects = ProjectsController()
    users = UsersController()


class SourcesController(RestController):
    """Works on sources."""

    def __init__(self):
        self._sources = None

    @property
    def sources(self):
        # FIXME(dhellmann): Add a configuration option for the filename.
        #
        # FIXME(dhellmann): We only want to load the file once in a process,
        # but we want to be able to mock the loading out in separate tests.
        #
        if not self._sources:
            self._sources = self._load_sources(os.path.abspath("sources.json"))
        return self._sources

    @staticmethod
    def _load_sources(filename):
        try:
            with open(filename, "r") as f:
                sources = jsonutils.load(f)
        except IOError as err:
            LOG.warning('Could not load data source definitions from %s: %s' %
                        (filename, err))
            sources = {}
        return sources

    @pecan.expose()
    def _lookup(self, source_id, *remainder):
        try:
            data = self.sources[source_id]
        except KeyError:
            # Unknown source
            pecan.abort(404, detail='No source %s' % source_id)
        return SourceController(source_id, data), remainder

    @wsme_pecan.wsexpose([Source])
    def get_all(self):
        return [Source(name=key, data=value)
                for key, value in self.sources.iteritems()]


class V2Controller(object):
    """Version 2 API controller root."""

    projects = ProjectsController()
    resources = ResourcesController()
    sources = SourcesController()
    users = UsersController()
    meters = MetersController()
