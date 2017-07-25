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

from neutronclient.common import exceptions
from neutronclient.v2_0 import client as clientv20
from oslo_config import cfg
from oslo_log import log

from ceilometer import keystone_client

SERVICE_OPTS = [
    cfg.StrOpt('neutron',
               default='network',
               help='Neutron service type.'),
    cfg.StrOpt('neutron_lbaas_version',
               default='v2',
               choices=('v1', 'v2'),
               help='Neutron load balancer version.')
]

LOG = log.getLogger(__name__)


def logged(func):

    @functools.wraps(func)
    def with_logging(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except exceptions.NeutronClientException as e:
            if e.status_code == 404:
                LOG.warning("The resource could not be found.")
            else:
                LOG.warning(e)
            return []
        except Exception as e:
            LOG.exception(e)
            raise

    return with_logging


class Client(object):
    """A client which gets information via python-neutronclient."""

    def __init__(self, conf):
        creds = conf.service_credentials
        params = {
            'session': keystone_client.get_session(conf),
            'endpoint_type': creds.interface,
            'region_name': creds.region_name,
            'service_type': conf.service_types.neutron,
        }
        self.client = clientv20.Client(**params)
        self.lb_version = conf.service_types.neutron_lbaas_version

    @logged
    def port_get_all(self):
        resp = self.client.list_ports()
        return resp.get('ports')

    @logged
    def vip_get_all(self):
        resp = self.client.list_vips()
        return resp.get('vips')

    @logged
    def pool_get_all(self):
        resources = []
        if self.lb_version == 'v1':
            resp = self.client.list_pools()
            resources = resp.get('pools')
        elif self.lb_version == 'v2':
            resources = self.list_pools_v2()
        return resources

    @logged
    def member_get_all(self):
        resources = []
        if self.lb_version == 'v1':
            resp = self.client.list_members()
            resources = resp.get('members')
        elif self.lb_version == 'v2':
            resources = self.list_members_v2()
        return resources

    @logged
    def health_monitor_get_all(self):
        resources = []
        if self.lb_version == 'v1':
            resp = self.client.list_health_monitors()
            resources = resp.get('health_monitors')
        elif self.lb_version == 'v2':
            resources = self.list_health_monitors_v2()
        return resources

    @logged
    def pool_stats(self, pool):
        return self.client.retrieve_pool_stats(pool)

    @logged
    def vpn_get_all(self):
        resp = self.client.list_vpnservices()
        return resp.get('vpnservices')

    @logged
    def ipsec_site_connections_get_all(self):
        resp = self.client.list_ipsec_site_connections()
        return resp.get('ipsec_site_connections')

    @logged
    def firewall_get_all(self):
        resp = self.client.list_firewalls()
        return resp.get('firewalls')

    @logged
    def fw_policy_get_all(self):
        resp = self.client.list_firewall_policies()
        return resp.get('firewall_policies')

    @logged
    def fip_get_all(self):
        fips = self.client.list_floatingips()['floatingips']
        return fips

    @logged
    def list_pools_v2(self):
        """This method is used to get the pools list.

        This method uses Load Balancer v2_0 API to achieve
        the detailed list of the pools.

        :returns: The list of the pool resources
        """
        pool_status = dict()
        resp = self.client.list_lbaas_pools()
        temp_pools = resp.get('pools')
        resources = []
        pool_listener_dict = self._get_pool_and_listener_ids(temp_pools)
        for k, v in pool_listener_dict.items():
            loadbalancer_id = self._get_loadbalancer_id_with_listener_id(v)
            status = self._get_pool_status(loadbalancer_id, v)
            for k, v in status.items():
                pool_status[k] = v

        for pool in temp_pools:
            pool_id = pool.get('id')
            pool['status'] = pool_status[pool_id]
            pool['lb_method'] = pool.get('lb_algorithm')
            pool['status_description'] = pool['status']
            # Based on the LBaaSv2 design, the properties 'vip_id'
            # and 'subnet_id' should belong to the loadbalancer resource and
            # not to the pool resource. However, because we don't want to
            # change the metadata of the pool resource this release,
            # we set them to empty values manually.
            pool['provider'] = ''
            pool['vip_id'] = ''
            pool['subnet_id'] = ''
            resources.append(pool)

        return resources

    @logged
    def list_members_v2(self):
        """Method is used to list the members info.

        This method is used to get the detailed list of the members
        with Load Balancer v2_0 API

        :returns: The list of the member resources
        """
        resources = []
        pools = self.client.list_lbaas_pools().get('pools')
        for pool in pools:
            pool_id = pool.get('id')
            listeners = pool.get('listeners')
            if not listeners:
                continue
            # NOTE(sileht): Can we have more than 1 listener
            listener_id = listeners[0].get('id')
            lb_id = self._get_loadbalancer_id_with_listener_id(listener_id)
            status = self._get_member_status(lb_id, [listener_id, pool_id])
            resp = self.client.list_lbaas_members(pool_id)
            temp_members = resp.get('members')
            for member in temp_members:
                member['status'] = status[member.get('id')]
                member['pool_id'] = pool_id
                member['status_description'] = member['status']
                resources.append(member)
        return resources

    @logged
    def list_health_monitors_v2(self):
        """Method is used to list the health monitors

        This method is used to get the detailed list of the health
        monitors with Load Balancer v2_0

        :returns: The list of the health monitor resources
        """
        resp = self.client.list_lbaas_healthmonitors()
        resources = resp.get('healthmonitors')
        return resources

    def _get_pool_and_listener_ids(self, pools):
        """Method is used to get the mapping between pool and listener

        This method is used to get the pool ids and listener ids
        from the pool list.

        :param pools: The list of the polls
        :returns: The relationship between pool and listener.
        It's a dictionary type. The key of this dict is
        the id of pool and the value of it is the id of the first
        listener which the pool belongs to
        """
        pool_listener_dict = dict()
        for pool in pools:
            key = pool.get("id")
            value = pool.get('listeners')[0].get('id')
            pool_listener_dict[key] = value
        return pool_listener_dict

    def _retrieve_loadbalancer_status_tree(self, loadbalancer_id):
        """Method is used to get the status of a LB.

        This method is used to get the status tree of a specific
        Load Balancer.

        :param loadbalancer_id: The ID of the specific Load
        Balancer.
        :returns: The status of the specific Load Balancer.
        It consists of the load balancer and all of its
        children's provisioning and operating statuses
        """
        lb_status_tree = self.client.retrieve_loadbalancer_status(
            loadbalancer_id)
        return lb_status_tree

    def _get_loadbalancer_id_with_listener_id(self, listener_id):
        """This method is used to get the loadbalancer id.

        :param listener_id: The ID of the listener
        :returns: The ID of the Loadbalancer
        """
        listener = self.client.show_listener(listener_id)
        listener_lbs = listener.get('listener').get('loadbalancers')
        loadbalancer_id = listener_lbs[0].get('id')
        return loadbalancer_id

    def _get_member_status(self, loadbalancer_id, parent_id):
        """Method used to get the status of member resource.

        This method is used to get the status of member
        resource belonged to the specific Load Balancer.

        :param loadbalancer_id: The ID of the Load Balancer.
        :param parent_id: The parent ID list of the member resource.
        For the member resource, the parent_id should be [listener_id,
        pool_id].
        :returns: The status dictionary of the member
        resource. The key is the ID of the member. The value is
        the operating status of the member resource.
        """
        # FIXME(liamji) the following meters are experimental and
        # may generate a large load against neutron api. The future
        # enhancements can be tracked against:
        # https://review.openstack.org/#/c/218560.
        # After it has been merged and the neutron client supports
        # with the corresponding apis, will change to use the new
        # method to get the status of the members.
        resp = self._retrieve_loadbalancer_status_tree(loadbalancer_id)
        status_tree = resp.get('statuses').get('loadbalancer')
        status_dict = dict()

        listeners_status = status_tree.get('listeners')
        for listener_status in listeners_status:
            listener_id = listener_status.get('id')
            if listener_id == parent_id[0]:
                pools_status = listener_status.get('pools')
                for pool_status in pools_status:
                    if pool_status.get('id') == parent_id[1]:
                        members_status = pool_status.get('members')
                        for member_status in members_status:
                            key = member_status.get('id')
                            # If the item has no the property 'id', skip
                            # it.
                            if key is None:
                                continue
                            # The situation that the property
                            # 'operating_status' is none is handled in
                            # the method get_sample() in lbaas.py.
                            value = member_status.get('operating_status')
                            status_dict[key] = value
                        break
                break

        return status_dict

    def _get_listener_status(self, loadbalancer_id):
        """Method used to get the status of the listener resource.

        This method is used to get the status of the listener
        resources belonged to the specific Load Balancer.

        :param loadbalancer_id: The ID of the Load Balancer.
        :returns: The status dictionary of the listener
        resource. The key is the ID of the listener resource. The
        value is the operating status of the listener resource.
        """
        # FIXME(liamji) the following meters are experimental and
        # may generate a large load against neutron api. The future
        # enhancements can be tracked against:
        # https://review.openstack.org/#/c/218560.
        # After it has been merged and the neutron client supports
        # with the corresponding apis, will change to use the new
        # method to get the status of the listeners.
        resp = self._retrieve_loadbalancer_status_tree(loadbalancer_id)
        status_tree = resp.get('statuses').get('loadbalancer')
        status_dict = dict()

        listeners_status = status_tree.get('listeners')
        for listener_status in listeners_status:
            key = listener_status.get('id')
            # If the item has no the property 'id', skip
            # it.
            if key is None:
                continue
            # The situation that the property
            # 'operating_status' is none is handled in
            # the method get_sample() in lbaas.py.
            value = listener_status.get('operating_status')
            status_dict[key] = value

        return status_dict

    def _get_pool_status(self, loadbalancer_id, parent_id):
        """Method used to get the status of pool resource.

        This method is used to get the status of the pool
        resources belonged to the specific Load Balancer.

        :param loadbalancer_id: The ID of the Load Balancer.
        :param parent_id: The parent ID of the pool resource.
        :returns: The status dictionary of the pool resource.
        The key is the ID of the pool resource. The value is
        the operating status of the pool resource.
        """
        # FIXME(liamji) the following meters are experimental and
        # may generate a large load against neutron api. The future
        # enhancements can be tracked against:
        # https://review.openstack.org/#/c/218560.
        # After it has been merged and the neutron client supports
        # with the corresponding apis, will change to use the new
        # method to get the status of the pools.
        resp = self._retrieve_loadbalancer_status_tree(loadbalancer_id)
        status_tree = resp.get('statuses').get('loadbalancer')
        status_dict = dict()

        listeners_status = status_tree.get('listeners')
        for listener_status in listeners_status:
            listener_id = listener_status.get('id')
            if listener_id == parent_id:
                pools_status = listener_status.get('pools')
                for pool_status in pools_status:
                    key = pool_status.get('id')
                    # If the item has no the property 'id', skip
                    # it.
                    if key is None:
                        continue
                    # The situation that the property
                    # 'operating_status' is none is handled in
                    # the method get_sample() in lbaas.py.
                    value = pool_status.get('operating_status')
                    status_dict[key] = value
                break

        return status_dict

    @logged
    def list_listener(self):
        """This method is used to get the list of the listeners."""
        resources = []
        if self.lb_version == 'v2':
            # list_listeners works only with lbaas v2 extension
            resp = self.client.list_listeners()
            resources = resp.get('listeners')
            for listener in resources:
                loadbalancer_id = listener.get('loadbalancers')[0].get('id')
                status = self._get_listener_status(loadbalancer_id)
                listener['operating_status'] = status[listener.get('id')]
        return resources

    @logged
    def list_loadbalancer(self):
        """This method is used to get the list of the loadbalancers."""
        resources = []
        if self.lb_version == 'v2':
            # list_loadbalancers works only with lbaas v2 extension
            resp = self.client.list_loadbalancers()
            resources = resp.get('loadbalancers')
        return resources

    @logged
    def get_loadbalancer_stats(self, loadbalancer_id):
        """This method is used to get the statistics of the loadbalancer.

        :param loadbalancer_id: the ID of the specified loadbalancer
        """
        resp = self.client.retrieve_loadbalancer_stats(loadbalancer_id)
        resource = resp.get('stats')
        return resource
