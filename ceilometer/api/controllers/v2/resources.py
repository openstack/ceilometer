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

import datetime
from six.moves import urllib

import pecan
from pecan import rest
import six
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from ceilometer.api.controllers.v2 import base
from ceilometer.api.controllers.v2 import utils
from ceilometer.api import rbac
from ceilometer.i18n import _


class Resource(base.Base):
    """An externally defined object for which samples have been received."""

    resource_id = wtypes.text
    "The unique identifier for the resource"

    project_id = wtypes.text
    "The ID of the owning project or tenant"

    user_id = wtypes.text
    "The ID of the user who created the resource or updated it last"

    first_sample_timestamp = datetime.datetime
    "UTC date & time not later than the first sample known for this resource"

    last_sample_timestamp = datetime.datetime
    "UTC date & time not earlier than the last sample known for this resource"

    metadata = {wtypes.text: wtypes.text}
    "Arbitrary metadata associated with the resource"

    links = [base.Link]
    "A list containing a self link and associated meter links"

    source = wtypes.text
    "The source where the resource come from"

    def __init__(self, metadata=None, **kwds):
        metadata = metadata or {}
        metadata = utils.flatten_metadata(metadata)
        super(Resource, self).__init__(metadata=metadata, **kwds)

    @classmethod
    def sample(cls):
        return cls(
            resource_id='bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
            project_id='35b17138-b364-4e6a-a131-8f3099c5be68',
            user_id='efd87807-12d2-4b38-9c70-5f5c2ac427ff',
            timestamp=datetime.datetime(2015, 1, 1, 12, 0, 0, 0),
            source="openstack",
            metadata={'name1': 'value1',
                      'name2': 'value2'},
            links=[
                base.Link(href=('http://localhost:8777/v2/resources/'
                                'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36'),
                          rel='self'),
                base.Link(href=('http://localhost:8777/v2/meters/volume?'
                                'q.field=resource_id&q.value='
                                'bd9431c1-8d69-4ad3-803a-8d4a6b89fd36'),
                          rel='volume')
            ],
        )


class ResourcesController(rest.RestController):
    """Works on resources."""

    @staticmethod
    def _make_link(rel_name, url, type, type_arg, query=None):
        query_str = ''
        if query:
            query_str = '?q.field=%s&q.value=%s' % (query['field'],
                                                    query['value'])
        return base.Link(href='%s/v2/%s/%s%s' % (url, type,
                                                 type_arg, query_str),
                         rel=rel_name)

    def _resource_links(self, resource_id, meter_links=1):
        links = [self._make_link('self', pecan.request.application_url,
                                 'resources', resource_id)]
        if meter_links:
            for meter in pecan.request.storage_conn.get_meters(
                    resource=resource_id):
                query = {'field': 'resource_id', 'value': resource_id}
                links.append(self._make_link(meter.name,
                                             pecan.request.application_url,
                                             'meters', meter.name,
                                             query=query))
        return links

    @wsme_pecan.wsexpose(Resource, six.text_type)
    def get_one(self, resource_id):
        """Retrieve details about one resource.

        :param resource_id: The UUID of the resource.
        """

        rbac.enforce('get_resource', pecan.request)
        # In case we have special character in resource id, for example, swift
        # can generate samples with resource id like
        # 29f809d9-88bb-4c40-b1ba-a77a1fcf8ceb/glance
        resource_id = urllib.parse.unquote(resource_id)

        authorized_project = rbac.get_limited_to_project(pecan.request.headers)
        resources = list(pecan.request.storage_conn.get_resources(
            resource=resource_id, project=authorized_project))
        if not resources:
            raise base.EntityNotFound(_('Resource'), resource_id)
        return Resource.from_db_and_links(resources[0],
                                          self._resource_links(resource_id))

    @wsme_pecan.wsexpose([Resource], [base.Query], int, int)
    def get_all(self, q=None, limit=None, meter_links=1):
        """Retrieve definitions of all of the resources.

        :param q: Filter rules for the resources to be returned.
        :param limit: Maximum number of resources to return.
        :param meter_links: option to include related meter links.
        """

        rbac.enforce('get_resources', pecan.request)

        q = q or []
        limit = utils.enforce_limit(limit)
        kwargs = utils.query_to_kwargs(
            q, pecan.request.storage_conn.get_resources, ['limit'])
        resources = [
            Resource.from_db_and_links(r,
                                       self._resource_links(r.resource_id,
                                                            meter_links))
            for r in pecan.request.storage_conn.get_resources(limit=limit,
                                                              **kwargs)]
        return resources
