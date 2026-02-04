# Copyright (C) 2014 eNovance SAS <licensing@enovance.com>
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

import functools

from openstack import connection
from openstack import exceptions as os_exc
from oslo_config import cfg
from oslo_log import log

from ceilometer import keystone_client

SERVICE_OPTS = [
    cfg.StrOpt('neutron',
               default='network',
               help='Neutron service type.'),
]

LOG = log.getLogger(__name__)


def logged(func):
    """Decorator to log exceptions from openstacksdk calls."""

    @functools.wraps(func)
    def with_logging(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except os_exc.HttpException as e:
            if e.status_code == 404:
                LOG.warning("The resource could not be found.")
            else:
                LOG.warning(e)
            return []
        except Exception as e:
            LOG.exception(e)
            raise

    return with_logging


class Client:
    """A client which gets information via openstacksdk."""

    def __init__(self, conf):
        """Initialize the Neutron client using openstacksdk.

        :param conf: Oslo config object with service credentials.
        """
        creds = conf.service_credentials
        params = {
            'session': keystone_client.get_session(conf),
            'endpoint_type': creds.interface,
            'region_name': creds.region_name,
            'service_type': conf.service_types.neutron,
        }
        self.conn = connection.Connection(conf=conf, **params)

    @logged
    def vpn_get_all(self):
        """Get all VPN services."""
        return [vpn.to_dict() for vpn in self.conn.network.vpn_services()]

    @logged
    def ipsec_site_connections_get_all(self):
        """Get all IPSec site connections."""
        return [conn.to_dict()
                for conn in self.conn.network.vpn_ipsec_site_connections()]

    @logged
    def firewall_get_all(self):
        """Get all firewall groups (FWaaS v2)."""
        return [fw.to_dict()
                for fw in self.conn.network.firewall_groups()]

    @logged
    def fw_policy_get_all(self):
        """Get all firewall policies."""
        return [policy.to_dict()
                for policy in self.conn.network.firewall_policies()]

    @logged
    def fip_get_all(self):
        """Get all floating IPs."""
        return [fip.to_dict() for fip in self.conn.network.ips()]
