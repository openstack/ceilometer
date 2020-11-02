#
# Copyright 2013 Intel Corp.
# Copyright 2013-2014 eNovance
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

from oslo_log import log
from oslo_utils import netutils
from stevedore import driver


LOG = log.getLogger(__name__)


def get_publisher(conf, url, namespace):
    """Get publisher driver and load it.

    :param url: URL for the publisher
    :param namespace: Namespace to use to look for drivers.
    """
    parse_result = netutils.urlsplit(url)
    loaded_driver = driver.DriverManager(namespace, parse_result.scheme)
    return loaded_driver.driver(conf, parse_result)


class ConfigPublisherBase(object, metaclass=abc.ABCMeta):
    """Base class for plugins that publish data."""

    def __init__(self, conf, parsed_url):
        self.conf = conf

    @abc.abstractmethod
    def publish_samples(self, samples):
        """Publish samples into final conduit."""

    @abc.abstractmethod
    def publish_events(self, events):
        """Publish events into final conduit."""
