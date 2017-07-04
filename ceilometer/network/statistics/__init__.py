#
# Copyright 2014 NEC Corporation.  All rights reserved.
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

import abc

from oslo_utils import netutils
import six
from six.moves.urllib import parse as urlparse
from stevedore import driver as _driver

from ceilometer.agent import plugin_base
from ceilometer import sample


@six.add_metaclass(abc.ABCMeta)
class _Base(plugin_base.PollsterBase):

    NAMESPACE = 'network.statistics.drivers'
    drivers = {}

    @property
    def default_discovery(self):
        # this signifies that the pollster gets its resources from
        # elsewhere, in this case they're manually listed in the
        # pipeline configuration
        return None

    @abc.abstractproperty
    def meter_name(self):
        """Return a Meter Name."""

    @abc.abstractproperty
    def meter_type(self):
        """Return a Meter Type."""

    @abc.abstractproperty
    def meter_unit(self):
        """Return a Meter Unit."""

    @staticmethod
    def _parse_my_resource(resource):

        parse_url = netutils.urlsplit(resource)

        params = urlparse.parse_qs(parse_url.query)
        parts = urlparse.ParseResult(parse_url.scheme,
                                     parse_url.netloc,
                                     parse_url.path,
                                     None,
                                     None,
                                     None)
        return parts, params

    @staticmethod
    def get_driver(conf, scheme):
        if scheme not in _Base.drivers:
            _Base.drivers[scheme] = _driver.DriverManager(_Base.NAMESPACE,
                                                          scheme).driver(conf)
        return _Base.drivers[scheme]

    def get_samples(self, manager, cache, resources):
        resources = resources or []
        for resource in resources:
            parse_url, params = self._parse_my_resource(resource)
            ext = self.get_driver(self.conf, parse_url.scheme)
            sample_data = ext.get_sample_data(self.meter_name,
                                              parse_url,
                                              params,
                                              cache)

            for data in sample_data or []:
                if data is None:
                    continue
                if not isinstance(data, list):
                    data = [data]
                for (volume, resource_id,
                     resource_metadata, project_id) in data:

                    yield sample.Sample(
                        name=self.meter_name,
                        type=self.meter_type,
                        unit=self.meter_unit,
                        volume=volume,
                        user_id=None,
                        project_id=project_id,
                        resource_id=resource_id,
                        resource_metadata=resource_metadata
                    )
