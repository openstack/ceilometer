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

import copy
import datetime
import inspect

from oslo_log import log
from oslo_utils import timeutils
import pecan
import six
import wsme

from ceilometer.api.controllers.v2 import base
from ceilometer.api import rbac
from ceilometer.i18n import _
from ceilometer import utils

LOG = log.getLogger(__name__)


def enforce_limit(limit):
    """Ensure limit is defined and is valid. if not, set a default."""
    if limit is None:
        limit = pecan.request.cfg.api.default_api_return_limit
        LOG.info('No limit value provided, result set will be'
                 ' limited to %(limit)d.', {'limit': limit})
    if not limit or limit <= 0:
        raise base.ClientSideError(_("Limit must be positive"))
    return limit


def get_auth_project(on_behalf_of=None):
    auth_project = rbac.get_limited_to_project(pecan.request.headers)
    created_by = pecan.request.headers.get('X-Project-Id')
    is_admin = auth_project is None

    if is_admin and on_behalf_of != created_by:
        auth_project = on_behalf_of
    return auth_project


def sanitize_query(query, db_func, on_behalf_of=None):
    """Check the query.

    See if:
    1) the request is coming from admin - then allow full visibility
    2) non-admin - make sure that the query includes the requester's project.
    """
    q = copy.copy(query)

    auth_project = get_auth_project(on_behalf_of)
    if auth_project:
        _verify_query_segregation(q, auth_project)

        proj_q = [i for i in q if i.field == 'project_id']
        valid_keys = inspect.getargspec(db_func)[0]
        if not proj_q and 'on_behalf_of' not in valid_keys:
            # The user is restricted, but they didn't specify a project
            # so add it for them.
            q.append(base.Query(field='project_id',
                                op='eq',
                                value=auth_project))
    return q


def _verify_query_segregation(query, auth_project=None):
    """Ensure non-admin queries are not constrained to another project."""
    auth_project = (auth_project or
                    rbac.get_limited_to_project(pecan.request.headers))

    if not auth_project:
        return

    for q in query:
        if q.field in ('project', 'project_id') and auth_project != q.value:
            raise base.ProjectNotAuthorized(q.value)


def validate_query(query, db_func, internal_keys=None,
                   allow_timestamps=True):
    """Validates the syntax of the query and verifies the query.

    Verification check if the query request is authorized for the included
    project.
    :param query: Query expression that should be validated
    :param db_func: the function on the storage level, of which arguments
        will form the valid_keys list, which defines the valid fields for a
        query expression
    :param internal_keys: internally used field names, that should not be
        used for querying
    :param allow_timestamps: defines whether the timestamp-based constraint is
        applicable for this query or not

    :raises InvalidInput: if an operator is not supported for a given field
    :raises InvalidInput: if timestamp constraints are allowed, but
        search_offset was included without timestamp constraint
    :raises: UnknownArgument: if a field name is not a timestamp field, nor
        in the list of valid keys
    """

    internal_keys = internal_keys or []
    _verify_query_segregation(query)

    valid_keys = inspect.getargspec(db_func)[0]

    internal_timestamp_keys = ['end_timestamp', 'start_timestamp',
                               'end_timestamp_op', 'start_timestamp_op']
    if 'start_timestamp' in valid_keys:
        internal_keys += internal_timestamp_keys
        valid_keys += ['timestamp', 'search_offset']
    internal_keys.append('self')
    internal_keys.append('metaquery')
    valid_keys = set(valid_keys) - set(internal_keys)
    translation = {'user_id': 'user',
                   'project_id': 'project',
                   'resource_id': 'resource'}

    has_timestamp_query = _validate_timestamp_fields(query,
                                                     'timestamp',
                                                     ('lt', 'le', 'gt', 'ge'),
                                                     allow_timestamps)
    has_search_offset_query = _validate_timestamp_fields(query,
                                                         'search_offset',
                                                         'eq',
                                                         allow_timestamps)

    if has_search_offset_query and not has_timestamp_query:
        raise wsme.exc.InvalidInput('field', 'search_offset',
                                    "search_offset cannot be used without " +
                                    "timestamp")

    def _is_field_metadata(field):
        return (field.startswith('metadata.') or
                field.startswith('resource_metadata.'))

    for i in query:
        if i.field not in ('timestamp', 'search_offset'):
            key = translation.get(i.field, i.field)
            operator = i.op
            if key in valid_keys or _is_field_metadata(i.field):
                if operator == 'eq':
                    if key == 'enabled':
                        i._get_value_as_type('boolean')
                    elif _is_field_metadata(key):
                        i._get_value_as_type()
                else:
                    raise wsme.exc.InvalidInput('op', i.op,
                                                'unimplemented operator for '
                                                '%s' % i.field)
            else:
                msg = ("unrecognized field in query: %s, "
                       "valid keys: %s") % (query, sorted(valid_keys))
                raise wsme.exc.UnknownArgument(key, msg)


def _validate_timestamp_fields(query, field_name, operator_list,
                               allow_timestamps):
    """Validates the timestamp related constraints in a query if there are any.

    :param query: query expression that may contain the timestamp fields
    :param field_name: timestamp name, which should be checked (timestamp,
        search_offset)
    :param operator_list: list of operators that are supported for that
        timestamp, which was specified in the parameter field_name
    :param allow_timestamps: defines whether the timestamp-based constraint is
        applicable to this query or not

    :returns: True, if there was a timestamp constraint, containing
        a timestamp field named as defined in field_name, in the query and it
        was allowed and syntactically correct.
    :returns: False, if there wasn't timestamp constraint, containing a
        timestamp field named as defined in field_name, in the query

    :raises InvalidInput: if an operator is unsupported for a given timestamp
        field
    :raises UnknownArgument: if the timestamp constraint is not allowed in
        the query
    """

    for item in query:
        if item.field == field_name:
            # If *timestamp* or *search_offset* field was specified in the
            # query, but timestamp is not supported on that resource, on
            # which the query was invoked, then raise an exception.
            if not allow_timestamps:
                raise wsme.exc.UnknownArgument(field_name,
                                               "not valid for " +
                                               "this resource")
            if item.op not in operator_list:
                raise wsme.exc.InvalidInput('op', item.op,
                                            'unimplemented operator for %s' %
                                            item.field)
            return True
    return False


def query_to_kwargs(query, db_func, internal_keys=None,
                    allow_timestamps=True):
    validate_query(query, db_func, internal_keys=internal_keys,
                   allow_timestamps=allow_timestamps)
    query = sanitize_query(query, db_func)
    translation = {'user_id': 'user',
                   'project_id': 'project',
                   'resource_id': 'resource'}
    stamp = {}
    metaquery = {}
    kwargs = {}
    for i in query:
        if i.field == 'timestamp':
            if i.op in ('lt', 'le'):
                stamp['end_timestamp'] = i.value
                stamp['end_timestamp_op'] = i.op
            elif i.op in ('gt', 'ge'):
                stamp['start_timestamp'] = i.value
                stamp['start_timestamp_op'] = i.op
        else:
            if i.op == 'eq':
                if i.field == 'search_offset':
                    stamp['search_offset'] = i.value
                elif i.field == 'enabled':
                    kwargs[i.field] = i._get_value_as_type('boolean')
                elif i.field.startswith('metadata.'):
                    metaquery[i.field] = i._get_value_as_type()
                elif i.field.startswith('resource_metadata.'):
                    metaquery[i.field[9:]] = i._get_value_as_type()
                else:
                    key = translation.get(i.field, i.field)
                    kwargs[key] = i.value

    if metaquery and 'metaquery' in inspect.getargspec(db_func)[0]:
        kwargs['metaquery'] = metaquery
    if stamp:
        kwargs.update(_get_query_timestamps(stamp))
    return kwargs


def _get_query_timestamps(args=None):
    """Return any optional timestamp information in the request.

    Determine the desired range, if any, from the GET arguments. Set
    up the query range using the specified offset.

    [query_start ... start_timestamp ... end_timestamp ... query_end]

    Returns a dictionary containing:

    start_timestamp: First timestamp to use for query
    start_timestamp_op: First timestamp operator to use for query
    end_timestamp: Final timestamp to use for query
    end_timestamp_op: Final timestamp operator to use for query
    """

    if args is None:
        return {}
    search_offset = int(args.get('search_offset', 0))

    def _parse_timestamp(timestamp):
        if not timestamp:
            return None
        try:
            iso_timestamp = timeutils.parse_isotime(timestamp)
            iso_timestamp = iso_timestamp.replace(tzinfo=None)
        except ValueError:
            raise wsme.exc.InvalidInput('timestamp', timestamp,
                                        'invalid timestamp format')
        return iso_timestamp

    start_timestamp = _parse_timestamp(args.get('start_timestamp'))
    end_timestamp = _parse_timestamp(args.get('end_timestamp'))
    start_timestamp = start_timestamp - datetime.timedelta(
        minutes=search_offset) if start_timestamp else None
    end_timestamp = end_timestamp + datetime.timedelta(
        minutes=search_offset) if end_timestamp else None
    return {'start_timestamp': start_timestamp,
            'end_timestamp': end_timestamp,
            'start_timestamp_op': args.get('start_timestamp_op'),
            'end_timestamp_op': args.get('end_timestamp_op')}


def flatten_metadata(metadata):
    """Return flattened resource metadata.

    Metadata is returned with flattened nested structures (except nested sets)
    and with all values converted to unicode strings.
    """
    if metadata:
        # After changing recursive_keypairs` output we need to keep
        # flattening output unchanged.
        # Example: recursive_keypairs({'a': {'b':{'c':'d'}}}, '.')
        # output before: a.b:c=d
        # output now: a.b.c=d
        # So to keep the first variant just replace all dots except the first
        return dict((k.replace('.', ':').replace(':', '.', 1),
                     six.text_type(v))
                    for k, v in utils.recursive_keypairs(metadata,
                                                         separator='.')
                    if type(v) is not set)
    return {}
