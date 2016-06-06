#
# Copyright 2014 Cisco Systems,Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_log import log

from ceilometer.i18n import _
from ceilometer.network.services import base
from ceilometer import sample

LOG = log.getLogger(__name__)


class FirewallPollster(base.BaseServicesPollster):
    """Pollster to capture firewalls status samples."""

    FIELDS = ['admin_state_up',
              'description',
              'name',
              'status',
              'firewall_policy_id',
              ]

    @property
    def default_discovery(self):
        return 'fw_services'

    def get_samples(self, manager, cache, resources):
        resources = resources or []

        for fw in resources:
            LOG.debug("Firewall : %s" % fw)
            status = self.get_status_id(fw['status'])
            if status == -1:
                # unknown status, skip this sample
                LOG.warning(_("Unknown status %(stat)s received on fw %(id)s,"
                            "skipping sample") % {'stat': fw['status'],
                                                  'id': fw['id']})
                continue

            yield sample.Sample(
                name='network.services.firewall',
                type=sample.TYPE_GAUGE,
                unit='firewall',
                volume=status,
                user_id=None,
                project_id=fw['tenant_id'],
                resource_id=fw['id'],
                resource_metadata=self.extract_metadata(fw)
            )


class FirewallPolicyPollster(base.BaseServicesPollster):
    """Pollster to capture firewall policy samples."""

    FIELDS = ['name',
              'description',
              'name',
              'firewall_rules',
              'shared',
              'audited',
              ]

    @property
    def default_discovery(self):
        return 'fw_policy'

    def get_samples(self, manager, cache, resources):
        resources = resources or []

        for fw in resources:
            LOG.debug("Firewall Policy: %s" % fw)

            yield sample.Sample(
                name='network.services.firewall.policy',
                type=sample.TYPE_GAUGE,
                unit='firewall_policy',
                volume=1,
                user_id=None,
                project_id=fw['tenant_id'],
                resource_id=fw['id'],
                resource_metadata=self.extract_metadata(fw)
            )
