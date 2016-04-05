#
# Copyright 2013 Intel Corp.
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
import collections

import six


@six.add_metaclass(abc.ABCMeta)
class TransformerBase(object):
    """Base class for plugins that transform the sample."""

    def __init__(self, **kwargs):
        """Setup transformer.

        Each time a transformed is involved in a pipeline, a new transformer
        instance is created and chained into the pipeline. i.e. transformer
        instance is per pipeline. This helps if transformer need keep some
        cache and per-pipeline information.

        :param kwargs: The parameters that are defined in pipeline config file.
        """
        super(TransformerBase, self).__init__()

    @abc.abstractmethod
    def handle_sample(self, sample):
        """Transform a sample.

        :param sample: A sample.
        """

    @abc.abstractproperty
    def grouping_keys(self):
        """Keys used to group transformer."""

    @staticmethod
    def flush():
        """Flush samples cached previously."""
        return []


class Namespace(object):
    """Encapsulates the namespace.

    Encapsulation is done by wrapping the evaluation of the configured rule.
    This allows nested dicts to be accessed in the attribute style,
    and missing attributes to yield false when used in a boolean expression.
    """
    def __init__(self, seed):
        self.__dict__ = collections.defaultdict(lambda: Namespace({}))
        self.__dict__.update(seed)
        for k, v in six.iteritems(self.__dict__):
            if isinstance(v, dict):
                self.__dict__[k] = Namespace(v)

    def __getattr__(self, attr):
        return self.__dict__[attr]

    def __getitem__(self, key):
        return self.__dict__[key]

    def __nonzero__(self):
        return len(self.__dict__) > 0
    __bool__ = __nonzero__
