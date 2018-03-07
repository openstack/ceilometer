#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 IBM Corp.
# Copyright 2013 eNovance <licensing@enovance.com>
# Copyright Ericsson AB 2013. All rights reserved
# Copyright 2014 Hewlett-Packard Company
# Copyright 2015 Huawei Technologies Co., Ltd.
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

import base64
import datetime

from oslo_log import log
from oslo_utils import strutils
from oslo_utils import timeutils
import pecan
from pecan import rest
import six
import wsme
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from ceilometer.api.controllers.v2 import base
from ceilometer.api.controllers.v2 import utils as v2_utils
from ceilometer.api import rbac
from ceilometer.i18n import _
from ceilometer.publisher import utils as publisher_utils
from ceilometer import sample
from ceilometer import storage
from ceilometer.storage import base as storage_base
from ceilometer import utils

LOG = log.getLogger(__name__)


class OldSample(base.Base):
    """A single measurement for a given meter and resource.

    This class is deprecated in favor of Sample.
    """

    source = wtypes.text
    "The ID of the source that identifies where the sample comes from"

    counter_name = wsme.wsattr(wtypes.text, mandatory=True)
    "The name of the meter"
    # FIXME(dhellmann): Make this meter_name?

    counter_type = wsme.wsattr(wtypes.text, mandatory=True)
    "The type of the meter (see :ref:`measurements`)"
    # FIXME(dhellmann): Make this meter_type?

    counter_unit = wsme.wsattr(wtypes.text, mandatory=True)
    "The unit of measure for the value in counter_volume"
    # FIXME(dhellmann): Make this meter_unit?

    counter_volume = wsme.wsattr(float, mandatory=True)
    "The actual measured value"

    user_id = wtypes.text
    "The ID of the user who last triggered an update to the resource"

    project_id = wtypes.text
    "The ID of the project or tenant that owns the resource"

    resource_id = wsme.wsattr(wtypes.text, mandatory=True)
    "The ID of the :class:`Resource` for which the measurements are taken"

    timestamp = datetime.datetime
    "UTC date and time when the measurement was made"

    recorded_at = datetime.datetime
    "When the sample has been recorded."

    resource_metadata = {wtypes.text: wtypes.text}
    "Arbitrary metadata associated with the resource"

    message_id = wtypes.text
    "A unique identifier for the sample"

    def __init__(self, counter_volume=None, resource_metadata=None,
                 timestamp=None, **kwds):
        resource_metadata = resource_metadata or {}
        if counter_volume is not None:
            counter_volume = float(counter_volume)
        resource_metadata = v2_utils.flatten_metadata(resource_metadata)
        # this is to make it easier for clients to pass a timestamp in
        if timestamp and isinstance(timestamp, six.string_types):
            timestamp = timeutils.parse_isotime(timestamp)

        super(OldSample, self).__init__(counter_volume=counter_volume,
                                        resource_metadata=resource_metadata,
                                        timestamp=timestamp, **kwds)

        if self.resource_metadata in (wtypes.Unset, None):
            self.resource_metadata = {}

    @classmethod
    def sample(cls):
        return cls(source='openstack',
                   counter_name='instance',
                   counter_type='gauge',
                   counter_unit='instance',
                   counter_volume=1,
                   resource_id='bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
                   project_id='35b17138-b364-4e6a-a131-8f3099c5be68',
                   user_id='efd87807-12d2-4b38-9c70-5f5c2ac427ff',
                   recorded_at=datetime.datetime(2015, 1, 1, 12, 0, 0, 0),
                   timestamp=datetime.datetime(2015, 1, 1, 12, 0, 0, 0),
                   resource_metadata={'name1': 'value1',
                                      'name2': 'value2'},
                   message_id='5460acce-4fd6-480d-ab18-9735ec7b1996',
                   )


class Statistics(base.Base):
    """Computed statistics for a query."""

    groupby = {wtypes.text: wtypes.text}
    "Dictionary of field names for group, if groupby statistics are requested"

    unit = wtypes.text
    "The unit type of the data set"

    min = float
    "The minimum volume seen in the data"

    max = float
    "The maximum volume seen in the data"

    avg = float
    "The average of all of the volume values seen in the data"

    sum = float
    "The total of all of the volume values seen in the data"

    count = int
    "The number of samples seen"

    aggregate = {wtypes.text: float}
    "The selectable aggregate value(s)"

    duration = float
    "The difference, in seconds, between the oldest and newest timestamp"

    duration_start = datetime.datetime
    "UTC date and time of the earliest timestamp, or the query start time"

    duration_end = datetime.datetime
    "UTC date and time of the oldest timestamp, or the query end time"

    period = int
    "The difference, in seconds, between the period start and end"

    period_start = datetime.datetime
    "UTC date and time of the period start"

    period_end = datetime.datetime
    "UTC date and time of the period end"

    def __init__(self, start_timestamp=None, end_timestamp=None, **kwds):
        super(Statistics, self).__init__(**kwds)
        self._update_duration(start_timestamp, end_timestamp)

    def _update_duration(self, start_timestamp, end_timestamp):
        # "Clamp" the timestamps we return to the original time
        # range, excluding the offset.
        if (start_timestamp and
                self.duration_start and
                self.duration_start < start_timestamp):
            self.duration_start = start_timestamp
            LOG.debug('clamping min timestamp to range')
        if (end_timestamp and
                self.duration_end and
                self.duration_end > end_timestamp):
            self.duration_end = end_timestamp
            LOG.debug('clamping max timestamp to range')

        # If we got valid timestamps back, compute a duration in seconds.
        #
        # If the min > max after clamping then we know the
        # timestamps on the samples fell outside of the time
        # range we care about for the query, so treat them as
        # "invalid."
        #
        # If the timestamps are invalid, return None as a
        # sentinel indicating that there is something "funny"
        # about the range.
        if (self.duration_start and
                self.duration_end and
                self.duration_start <= self.duration_end):
            self.duration = timeutils.delta_seconds(self.duration_start,
                                                    self.duration_end)
        else:
            self.duration_start = self.duration_end = self.duration = None

    @classmethod
    def sample(cls):
        return cls(unit='GiB',
                   min=1,
                   max=9,
                   avg=4.5,
                   sum=45,
                   count=10,
                   duration_start=datetime.datetime(2013, 1, 4, 16, 42),
                   duration_end=datetime.datetime(2013, 1, 4, 16, 47),
                   period=7200,
                   period_start=datetime.datetime(2013, 1, 4, 16, 00),
                   period_end=datetime.datetime(2013, 1, 4, 18, 00),
                   )


class Aggregate(base.Base):

    func = wsme.wsattr(wtypes.text, mandatory=True)
    "The aggregation function name"

    param = wsme.wsattr(wtypes.text, default=None)
    "The paramter to the aggregation function"

    def __init__(self, **kwargs):
        super(Aggregate, self).__init__(**kwargs)

    @staticmethod
    def validate(aggregate):
        valid_agg = (storage_base.Connection.CAPABILITIES.get('statistics', {})
                     .get('aggregation', {}).get('selectable', {}).keys())
        if aggregate.func not in valid_agg:
            msg = _('Invalid aggregation function: %s') % aggregate.func
            raise base.ClientSideError(msg)
        return aggregate

    @classmethod
    def sample(cls):
        return cls(func='cardinality',
                   param='resource_id')


def _validate_groupby_fields(groupby_fields):
    """Checks that the list of groupby fields from request is valid.

    If all fields are valid, returns fields with duplicates removed.
    """
    # NOTE(terriyu): Currently, metadata fields are supported in our
    # group by statistics implementation only for mongodb
    valid_fields = set(['user_id', 'resource_id', 'project_id', 'source',
                        'resource_metadata.instance_type'])

    invalid_fields = set(groupby_fields) - valid_fields
    if invalid_fields:
        raise wsme.exc.UnknownArgument(invalid_fields,
                                       "Invalid groupby fields")

    # Remove duplicate fields
    # NOTE(terriyu): This assumes that we don't care about the order of the
    # group by fields.
    return list(set(groupby_fields))


class MeterController(rest.RestController):
    """Manages operations on a single meter."""
    _custom_actions = {
        'statistics': ['GET'],
    }

    def __init__(self, meter_name):
        pecan.request.context['meter_name'] = meter_name
        self.meter_name = meter_name

    @wsme_pecan.wsexpose([OldSample], [base.Query], int)
    def get_all(self, q=None, limit=None):
        """Return samples for the meter.

        :param q: Filter rules for the data to be returned.
        :param limit: Maximum number of samples to return.
        """

        rbac.enforce('get_samples', pecan.request)

        q = q or []
        limit = v2_utils.enforce_limit(limit)
        kwargs = v2_utils.query_to_kwargs(q, storage.SampleFilter.__init__)
        kwargs['meter'] = self.meter_name
        f = storage.SampleFilter(**kwargs)
        return [OldSample.from_db_model(e)
                for e in pecan.request.storage_conn.get_samples(f, limit=limit)
                ]

    @wsme_pecan.wsexpose([OldSample], str, body=[OldSample], status_code=201)
    def post(self, direct='', samples=None):
        """Post a list of new Samples to Telemetry.

        :param direct: a flag indicates whether the samples will be posted
                       directly to storage or not.
        :param samples: a list of samples within the request body.
        """
        rbac.enforce('create_samples', pecan.request)

        direct = strutils.bool_from_string(direct)
        if not samples:
            msg = _('Samples should be included in request body')
            raise base.ClientSideError(msg)

        now = timeutils.utcnow()
        auth_project = rbac.get_limited_to_project(pecan.request.headers)
        def_source = pecan.request.cfg.sample_source
        def_project_id = pecan.request.headers.get('X-Project-Id')
        def_user_id = pecan.request.headers.get('X-User-Id')

        published_samples = []
        for s in samples:
            if self.meter_name != s.counter_name:
                raise wsme.exc.InvalidInput('counter_name', s.counter_name,
                                            'should be %s' % self.meter_name)

            if s.message_id:
                raise wsme.exc.InvalidInput('message_id', s.message_id,
                                            'The message_id must not be set')

            if s.counter_type not in sample.TYPES:
                raise wsme.exc.InvalidInput('counter_type', s.counter_type,
                                            'The counter type must be: ' +
                                            ', '.join(sample.TYPES))

            s.user_id = (s.user_id or def_user_id)
            s.project_id = (s.project_id or def_project_id)
            s.source = '%s:%s' % (s.project_id, (s.source or def_source))
            s.timestamp = (s.timestamp or now)

            if auth_project and auth_project != s.project_id:
                # non admin user trying to cross post to another project_id
                auth_msg = 'can not post samples to other projects'
                raise wsme.exc.InvalidInput('project_id', s.project_id,
                                            auth_msg)

            published_sample = sample.Sample(
                name=s.counter_name,
                type=s.counter_type,
                unit=s.counter_unit,
                volume=s.counter_volume,
                user_id=s.user_id,
                project_id=s.project_id,
                resource_id=s.resource_id,
                timestamp=s.timestamp.isoformat(),
                resource_metadata=utils.restore_nesting(s.resource_metadata,
                                                        separator='.'),
                source=s.source)
            s.message_id = published_sample.id

            sample_dict = publisher_utils.meter_message_from_counter(
                published_sample,
                pecan.request.cfg.publisher.telemetry_secret)
            if direct:
                ts = timeutils.parse_isotime(sample_dict['timestamp'])
                sample_dict['timestamp'] = timeutils.normalize_time(ts)
                pecan.request.storage_conn.record_metering_data(sample_dict)
            else:
                published_samples.append(sample_dict)
        if not direct:
            pecan.request.notifier.sample(
                {'user': def_user_id,
                 'tenant': def_project_id,
                 'is_admin': True},
                'telemetry.api',
                {'samples': published_samples})

        return samples

    @wsme_pecan.wsexpose([Statistics],
                         [base.Query], [six.text_type], int, [Aggregate])
    def statistics(self, q=None, groupby=None, period=None, aggregate=None):
        """Computes the statistics of the samples in the time range given.

        :param q: Filter rules for the data to be returned.
        :param groupby: Fields for group by aggregation
        :param period: Returned result will be an array of statistics for a
                       period long of that number of seconds.
        :param aggregate: The selectable aggregation functions to be applied.
        """

        rbac.enforce('compute_statistics', pecan.request)

        q = q or []
        groupby = groupby or []
        aggregate = aggregate or []

        if period and period < 0:
            raise base.ClientSideError(_("Period must be positive."))

        kwargs = v2_utils.query_to_kwargs(q, storage.SampleFilter.__init__)
        kwargs['meter'] = self.meter_name
        f = storage.SampleFilter(**kwargs)
        g = _validate_groupby_fields(groupby)

        aggregate = utils.uniq(aggregate, ['func', 'param'])
        # Find the original timestamp in the query to use for clamping
        # the duration returned in the statistics.
        start = end = None
        for i in q:
            if i.field == 'timestamp' and i.op in ('lt', 'le'):
                end = timeutils.parse_isotime(i.value).replace(
                    tzinfo=None)
            elif i.field == 'timestamp' and i.op in ('gt', 'ge'):
                start = timeutils.parse_isotime(i.value).replace(
                    tzinfo=None)

        try:
            computed = pecan.request.storage_conn.get_meter_statistics(
                f, period, g, aggregate)
            return [Statistics(start_timestamp=start,
                               end_timestamp=end,
                               **c.as_dict())
                    for c in computed]
        except OverflowError as e:
            params = dict(period=period, err=e)
            raise base.ClientSideError(
                _("Invalid period %(period)s: %(err)s") % params)


class Meter(base.Base):
    """One category of measurements."""

    name = wtypes.text
    "The unique name for the meter"

    type = wtypes.Enum(str, *sample.TYPES)
    "The meter type (see :ref:`measurements`)"

    unit = wtypes.text
    "The unit of measure"

    resource_id = wtypes.text
    "The ID of the :class:`Resource` for which the measurements are taken"

    project_id = wtypes.text
    "The ID of the project or tenant that owns the resource"

    user_id = wtypes.text
    "The ID of the user who last triggered an update to the resource"

    source = wtypes.text
    "The ID of the source that identifies where the meter comes from"

    meter_id = wtypes.text
    "The unique identifier for the meter"

    def __init__(self, **kwargs):
        meter_id = '%s+%s' % (kwargs['resource_id'], kwargs['name'])
        # meter_id is of type Unicode but base64.encodestring() only accepts
        # strings. See bug #1333177
        meter_id = base64.b64encode(meter_id.encode('utf-8'))
        kwargs['meter_id'] = meter_id
        super(Meter, self).__init__(**kwargs)

    @classmethod
    def sample(cls):
        return cls(name='instance',
                   type='gauge',
                   unit='instance',
                   resource_id='bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
                   project_id='35b17138-b364-4e6a-a131-8f3099c5be68',
                   user_id='efd87807-12d2-4b38-9c70-5f5c2ac427ff',
                   source='openstack',
                   )


class MetersController(rest.RestController):
    """Works on meters."""

    @pecan.expose()
    def _lookup(self, meter_name, *remainder):
        return MeterController(meter_name), remainder

    @wsme_pecan.wsexpose([Meter], [base.Query], int, str)
    def get_all(self, q=None, limit=None, unique=''):
        """Return all known meters, based on the data recorded so far.

        :param q: Filter rules for the meters to be returned.
        :param limit: Maximum number of meters to be returned.
        :param unique: flag to indicate unique meters to be returned.
        """

        rbac.enforce('get_meters', pecan.request)

        q = q or []

        # Timestamp field is not supported for Meter queries
        limit = v2_utils.enforce_limit(limit)
        kwargs = v2_utils.query_to_kwargs(
            q, pecan.request.storage_conn.get_meters,
            ['limit'], allow_timestamps=False)
        return [Meter.from_db_model(m)
                for m in pecan.request.storage_conn.get_meters(
                limit=limit, unique=strutils.bool_from_string(unique),
                **kwargs)]
