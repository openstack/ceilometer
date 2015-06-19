#
# Copyright 2015 Mirantis Inc.
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
from ceilometer.dispatcher.resources import base


class Identity(base.ResourceBase):
    @staticmethod
    def get_resource_extra_attributes(sample):
        return {}

    @staticmethod
    def get_metrics_names():
        return ['identity.authenticate.success',
                'identity.authenticate.pending',
                'identity.authenticate.failure',
                'identity.user.created',
                'identity.user.deleted',
                'identity.user.updated',
                'identity.group.created',
                'identity.group.deleted',
                'identity.group.updated',
                'identity.role.created',
                'identity.role.deleted',
                'identity.role.updated',
                'identity.project.created',
                'identity.project.deleted',
                'identity.project.updated',
                'identity.trust.created',
                'identity.trust.deleted',
                'identity.role_assignment.created',
                'identity.role_assignment.deleted',
                ]
