# -*- encoding: utf-8 -*-
#
# Copyright © 2013 ZHAW SoE
# Copyright © 2014 Intel Corp.
#
# Authors: Lucas Graf <graflu0@students.zhaw.ch>
#          Toni Zehnder <zehndton@students.zhaw.ch>
#          Lianhao Lu <lianhao.lu@intel.com>
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
"""Base class for plugins used by the hardware agent."""

import abc
import itertools
import six

from ceilometer.central import plugin
from ceilometer.hardware import inspector as insloader
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import network_utils

LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class HardwarePollster(plugin.CentralPollster):
    """Base class for plugins that support the polling API."""

    CACHE_KEY = None
    INSPECT_METHOD = None

    def __init__(self):
        super(HardwarePollster, self).__init__()
        self.inspectors = {}

    def get_samples(self, manager, cache, resources=[]):
        """Return an iterable of Sample instances from polling the resources.

        :param manager: The service manager invoking the plugin
        :param cache: A dictionary for passing data between plugins
        :param resources: end point to poll data from
        """
        h_cache = cache.setdefault(self.CACHE_KEY, {})
        sample_iters = []
        for res in resources:
            parsed_url = network_utils.urlsplit(res)
            inspector = self._get_inspector(parsed_url)
            func = getattr(inspector, self.INSPECT_METHOD)

            try:
                # Call hardware inspector to poll for the data
                i_cache = h_cache.setdefault(res, {})
                if res not in i_cache:
                    i_cache[res] = list(func(parsed_url))
                # Generate samples
                if i_cache[res]:
                    sample_iters.append(self.generate_samples(parsed_url,
                                                              i_cache[res]))
            except Exception as err:
                LOG.exception(_('inspector call %(func)r failed for '
                                'host %(host)s: %(err)s'),
                              dict(func=func,
                                   host=parsed_url.hostname,
                                   err=err))
        return itertools.chain(*sample_iters)

    def generate_samples(self, host_url, data):
        """Generate an iterable Sample from the data returned by inspector

        :param host_url: host url of the endpoint
        :param data: list of data returned by the corresponding inspector

        """
        return (self.generate_one_sample(host_url, datum) for datum in data)

    @abc.abstractmethod
    def generate_one_sample(self, host_url, c_data):
        """Return one Sample.

        :param host_url: host url of the endpoint
        :param c_data: data returned by the corresponding inspector, of
                       one of the types defined in the file
                       ceilometer.hardware.inspector.base.CPUStats
        """

    def _get_inspector(self, parsed_url):
        if parsed_url.scheme not in self.inspectors:
            try:
                driver = insloader.get_inspector(parsed_url)
                self.inspectors[parsed_url.scheme] = driver
            except Exception as err:
                LOG.exception(_("Can NOT load inspector %(name)s: %(err)s"),
                              dict(name=parsed_url.scheme,
                                   err=err))
                raise err
        return self.inspectors[parsed_url.scheme]
