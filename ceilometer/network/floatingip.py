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

from oslo_config import cfg
from oslo_log import log
from oslo_utils import timeutils

from ceilometer.agent import plugin_base
from ceilometer.i18n import _LW
from ceilometer import neutron_client
from ceilometer import sample

LOG = log.getLogger(__name__)

cfg.CONF.import_group('service_types', 'ceilometer.neutron_client')


class FloatingIPPollster(plugin_base.PollsterBase):

    STATUS = {
        'inactive': 0,
        'active': 1,
        'pending_create': 2,
    }

    def __init__(self):
        self.neutron_cli = neutron_client.Client()

    @property
    def default_discovery(self):
        return 'endpoint:%s' % cfg.CONF.service_types.neutron

    @staticmethod
    def _form_metadata_for_fip(fip):
        """Return a metadata dictionary for the fip usage data."""
        metadata = {
            'router_id': fip.get("router_id"),
            'status': fip.get("status"),
            'floating_network_id': fip.get("floating_network_id"),
            'fixed_ip_address': fip.get("fixed_ip_address"),
            'port_id': fip.get("port_id"),
            'floating_ip_address': fip.get("floating_ip_address")
        }
        return metadata

    def get_samples(self, manager, cache, resources):

        for fip in self.neutron_cli.fip_get_all():
            status = self.STATUS.get(fip['status'].lower())
            if status is None:
                LOG.warning(_LW("Invalid status, skipping IP address %s") %
                            fip['floating_ip_address'])
                continue
            res_metadata = self._form_metadata_for_fip(fip)
            yield sample.Sample(
                name='ip.floating',
                type=sample.TYPE_GAUGE,
                unit='ip',
                volume=status,
                user_id=fip.get('user_id'),
                project_id=fip['tenant_id'],
                resource_id=fip['id'],
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata=res_metadata
            )
