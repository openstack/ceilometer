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
import uuid

import pecan
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from ceilometer.api.controllers.v2 import base
from ceilometer.api.controllers.v2 import utils
from ceilometer.api import rbac
from ceilometer.i18n import _
from ceilometer import sample
from ceilometer import storage


class Sample(base.Base):
    """One measurement."""

    id = wtypes.text
    "The unique identifier for the sample."

    meter = wtypes.text
    "The meter name this sample is for."

    type = wtypes.Enum(str, *sample.TYPES)
    "The meter type (see :ref:`meter_types`)"

    unit = wtypes.text
    "The unit of measure."

    volume = float
    "The metered value."

    user_id = wtypes.text
    "The user this sample was taken for."

    project_id = wtypes.text
    "The project this sample was taken for."

    resource_id = wtypes.text
    "The :class:`Resource` this sample was taken for."

    source = wtypes.text
    "The source that identifies where the sample comes from."

    timestamp = datetime.datetime
    "When the sample has been generated."

    recorded_at = datetime.datetime
    "When the sample has been recorded."

    metadata = {wtypes.text: wtypes.text}
    "Arbitrary metadata associated with the sample."

    @classmethod
    def from_db_model(cls, m):
        return cls(id=m.message_id,
                   meter=m.counter_name,
                   type=m.counter_type,
                   unit=m.counter_unit,
                   volume=m.counter_volume,
                   user_id=m.user_id,
                   project_id=m.project_id,
                   resource_id=m.resource_id,
                   source=m.source,
                   timestamp=m.timestamp,
                   recorded_at=m.recorded_at,
                   metadata=utils.flatten_metadata(m.resource_metadata))

    @classmethod
    def sample(cls):
        return cls(id=str(uuid.uuid1()),
                   meter='instance',
                   type='gauge',
                   unit='instance',
                   volume=1,
                   resource_id='bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
                   project_id='35b17138-b364-4e6a-a131-8f3099c5be68',
                   user_id='efd87807-12d2-4b38-9c70-5f5c2ac427ff',
                   timestamp=datetime.datetime(2015, 1, 1, 12, 0, 0, 0),
                   recorded_at=datetime.datetime(2015, 1, 1, 12, 0, 0, 0),
                   source='openstack',
                   metadata={'name1': 'value1',
                             'name2': 'value2'},
                   )


class SamplesController(rest.RestController):
    """Controller managing the samples."""

    @wsme_pecan.wsexpose([Sample], [base.Query], int)
    def get_all(self, q=None, limit=None):
        """Return all known samples, based on the data recorded so far.

        :param q: Filter rules for the samples to be returned.
        :param limit: Maximum number of samples to be returned.
        """

        rbac.enforce('get_samples', pecan.request)

        q = q or []

        limit = utils.enforce_limit(limit)
        kwargs = utils.query_to_kwargs(q, storage.SampleFilter.__init__)
        f = storage.SampleFilter(**kwargs)
        return map(Sample.from_db_model,
                   pecan.request.storage_conn.get_samples(f, limit=limit))

    @wsme_pecan.wsexpose(Sample, wtypes.text)
    def get_one(self, sample_id):
        """Return a sample.

        :param sample_id: the id of the sample.
        """

        rbac.enforce('get_sample', pecan.request)

        f = storage.SampleFilter(message_id=sample_id)

        samples = list(pecan.request.storage_conn.get_samples(f))
        if len(samples) < 1:
            raise base.EntityNotFound(_('Sample'), sample_id)

        return Sample.from_db_model(samples[0])
