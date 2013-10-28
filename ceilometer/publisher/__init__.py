# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Intel Corp.
# Copyright © 2013 eNovance
#
# Author: Yunhong Jiang <yunhong.jiang@intel.com>
#         Julien Danjou <julien@danjou.info>
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

import six
from stevedore import driver

from ceilometer.openstack.common import network_utils


def get_publisher(url, namespace='ceilometer.publisher'):
    """Get publisher driver and load it.

    :param URL: URL for the publisher
    :param namespace: Namespace to use to look for drivers.
    """
    parse_result = network_utils.urlsplit(url)
    loaded_driver = driver.DriverManager(namespace, parse_result.scheme)
    return loaded_driver.driver(parse_result)


@six.add_metaclass(abc.ABCMeta)
class PublisherBase(object):
    """Base class for plugins that publish the sampler."""

    def __init__(self, parsed_url):
        pass

    @abc.abstractmethod
    def publish_samples(self, context, samples):
        "Publish samples into final conduit."
