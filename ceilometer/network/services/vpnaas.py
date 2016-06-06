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


class VPNServicesPollster(base.BaseServicesPollster):
    """Pollster to capture VPN status samples."""

    FIELDS = ['admin_state_up',
              'description',
              'name',
              'status',
              'subnet_id',
              'router_id'
              ]

    @property
    def default_discovery(self):
        return 'vpn_services'

    def get_samples(self, manager, cache, resources):
        resources = resources or []

        for vpn in resources:
            LOG.debug("VPN : %s" % vpn)
            status = self.get_status_id(vpn['status'])
            if status == -1:
                # unknown status, skip this sample
                LOG.warning(_("Unknown status %(stat)s received on vpn "
                              "%(id)s, skipping sample")
                            % {'stat': vpn['status'], 'id': vpn['id']})
                continue

            yield sample.Sample(
                name='network.services.vpn',
                type=sample.TYPE_GAUGE,
                unit='vpnservice',
                volume=status,
                user_id=None,
                project_id=vpn['tenant_id'],
                resource_id=vpn['id'],
                resource_metadata=self.extract_metadata(vpn)
            )


class IPSecConnectionsPollster(base.BaseServicesPollster):
    """Pollster to capture vpn ipsec connections status samples."""

    FIELDS = ['name',
              'description',
              'peer_address',
              'peer_id',
              'peer_cidrs',
              'psk',
              'initiator',
              'ikepolicy_id',
              'dpd',
              'ipsecpolicy_id',
              'vpnservice_id',
              'mtu',
              'admin_state_up',
              'status',
              'tenant_id'
              ]

    @property
    def default_discovery(self):
        return 'ipsec_connections'

    def get_samples(self, manager, cache, resources):
        resources = resources or []

        for conn in resources:
            LOG.debug("IPSec Connection Info: %s" % conn)

            yield sample.Sample(
                name='network.services.vpn.connections',
                type=sample.TYPE_GAUGE,
                unit='ipsec_site_connection',
                volume=1,
                user_id=None,
                project_id=conn['tenant_id'],
                resource_id=conn['id'],
                resource_metadata=self.extract_metadata(conn)
            )
