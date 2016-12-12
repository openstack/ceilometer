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

import pecan
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from ceilometer.api.controllers.v2 import base
from ceilometer import utils


def _flatten_capabilities(capabilities):
    return dict((k, v) for k, v in utils.recursive_keypairs(capabilities))


class Capabilities(base.Base):
    """A representation of the API and storage capabilities.

    Usually constrained by restrictions imposed by the storage driver.
    """

    api = {wtypes.text: bool}
    "A flattened dictionary of API capabilities"
    storage = {wtypes.text: bool}
    "A flattened dictionary of storage capabilities"

    @classmethod
    def sample(cls):
        return cls(
            api=_flatten_capabilities({
                'meters': {'query': {'simple': True,
                                     'metadata': True}},
                'resources': {'query': {'simple': True,
                                        'metadata': True}},
                'samples': {'query': {'simple': True,
                                      'metadata': True,
                                      'complex': True}},
                'statistics': {'groupby': True,
                               'query': {'simple': True,
                                         'metadata': True},
                               'aggregation': {'standard': True,
                                               'selectable': {
                                                   'max': True,
                                                   'min': True,
                                                   'sum': True,
                                                   'avg': True,
                                                   'count': True,
                                                   'stddev': True,
                                                   'cardinality': True,
                                                   'quartile': False}}},
            }),
            storage=_flatten_capabilities(
                {'storage': {'production_ready': True}}),
        )


class CapabilitiesController(rest.RestController):
    """Manages capabilities queries."""

    @wsme_pecan.wsexpose(Capabilities)
    def get(self):
        """Returns a flattened dictionary of API capabilities.

        Capabilities supported by the currently configured storage driver.
        """
        # variation in API capabilities is effectively determined by
        # the lack of strict feature parity across storage drivers
        conn = pecan.request.storage_conn
        driver_capabilities = conn.get_capabilities().copy()
        driver_perf = conn.get_storage_capabilities()
        return Capabilities(api=_flatten_capabilities(driver_capabilities),
                            storage=_flatten_capabilities(driver_perf))
