# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
# Copyright © 2012 Red Hat, Inc
#
# Author: Julien Danjou <julien@danjou.info>
# Author: Eoghan Glynn <eglynn@redhat.com>
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

from ceilometer.compute import plugin
from ceilometer.compute.pollsters import util
from ceilometer import sample


class InstancePollster(plugin.ComputePollster):

    @staticmethod
    def get_samples(manager, cache, instance):
        yield util.make_sample_from_instance(
            instance,
            name='instance',
            type=sample.TYPE_GAUGE,
            unit='instance',
            volume=1,
        )


class InstanceFlavorPollster(plugin.ComputePollster):

    @staticmethod
    def get_samples(manager, cache, instance):
        yield util.make_sample_from_instance(
            instance,
            # Use the "meter name + variable" syntax
            name='instance:%s' %
            instance.flavor['name'],
            type=sample.TYPE_GAUGE,
            unit='instance',
            volume=1,
        )
