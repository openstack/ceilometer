# Copyright 2016 Sungard Availability Services
# Copyright 2016 Red Hat
# Copyright 2012 eNovance <licensing@enovance.com>
# Copyright 2013 IBM Corp
# All Rights Reserved.
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

from oslo_log import log

from ceilometer.network.services import base
from ceilometer import sample

LOG = log.getLogger(__name__)


class FloatingIPPollster(base.BaseServicesPollster):

    FIELDS = ['router_id',
              'status',
              'floating_network_id',
              'fixed_ip_address',
              'port_id',
              'floating_ip_address',
              ]

    @property
    def default_discovery(self):
        return 'fip_services'

    def get_samples(self, manager, cache, resources):

        for fip in resources or []:
            if fip['status'] is None:
                LOG.warning("Invalid status, skipping IP address %s" %
                            fip['floating_ip_address'])
                continue
            status = self.get_status_id(fip['status'])
            yield sample.Sample(
                name='ip.floating',
                type=sample.TYPE_GAUGE,
                unit='ip',
                volume=status,
                user_id=fip.get('user_id'),
                project_id=fip['tenant_id'],
                resource_id=fip['id'],
                resource_metadata=self.extract_metadata(fip)
            )
