# Copyright (C) 2026 Red Hat
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

from unittest import mock

from openstack import exceptions as os_exc
from oslotest import base

from ceilometer import neutron_client
from ceilometer import service
from ceilometer.tests.unit import fakes


class TestNeutronClient(base.BaseTestCase):
    """Tests for the Neutron client using openstacksdk."""

    def setUp(self):
        super().setUp()
        self.CONF = service.prepare_service([], [])

        self.mock_connection = mock.patch(
            'openstack.connection.Connection',
            autospec=True, return_value=fakes.FakeConnection())
        self.mock_conn_class = self.mock_connection.start()
        self.addCleanup(self.mock_connection.stop)

        # Create the client (uses mocked Connection)
        self.nc = neutron_client.Client(self.CONF)

    def test_fip_get_all(self):
        """Test getting all floating IPs returns list of dicts."""
        result = self.nc.fip_get_all()

        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], dict)
        self.assertEqual('fip-123', result[0]['id'])
        self.assertEqual('192.168.1.100', result[0]['floating_ip_address'])

    def test_fip_get_all_empty(self):
        """Test getting floating IPs when none exist."""
        self.nc.conn.network.ips = mock.Mock(return_value=iter([]))

        result = self.nc.fip_get_all()

        self.assertEqual([], result)

    def test_vpn_get_all(self):
        """Test getting all VPN services returns list of dicts."""

        result = self.nc.vpn_get_all()

        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], dict)
        self.assertEqual('vpn-123', result[0]['id'])
        self.assertEqual('my-vpn', result[0]['name'])

    def test_vpn_get_all_empty(self):
        """Test getting VPN services when none exist."""
        self.nc.conn.network.vpn_services = mock.Mock(
            return_value=iter([]))

        result = self.nc.vpn_get_all()

        self.assertEqual([], result)

    def test_ipsec_site_connections_get_all(self):
        """Test getting all IPSec site connections returns list of dicts."""

        result = self.nc.ipsec_site_connections_get_all()

        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], dict)
        self.assertEqual('ipsec-123', result[0]['id'])

    def test_ipsec_site_connections_get_all_empty(self):
        """Test getting IPSec connections when none exist."""
        self.nc.conn.network.vpn_ipsec_site_connections =\
            mock.Mock(return_value=iter([]))

        result = self.nc.ipsec_site_connections_get_all()

        self.assertEqual([], result)

    def test_firewall_get_all(self):
        """Test getting all firewall groups returns list of dicts."""

        result = self.nc.firewall_get_all()

        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], dict)
        self.assertEqual('fw-123', result[0]['id'])
        self.assertEqual('my-firewall', result[0]['name'])

    def test_firewall_get_all_empty(self):
        """Test getting firewall groups when none exist."""
        self.nc.conn.network.firewall_groups = mock.Mock(
            return_value=iter([]))

        result = self.nc.firewall_get_all()

        self.assertEqual([], result)

    def test_fw_policy_get_all(self):
        """Test getting all firewall policies returns list of dicts."""

        result = self.nc.fw_policy_get_all()

        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], dict)
        self.assertEqual('policy-123', result[0]['id'])
        self.assertEqual('my-policy', result[0]['name'])

    def test_fw_policy_get_all_empty(self):
        """Test getting firewall policies when none exist."""
        self.nc.conn.network.firewall_policies = mock.Mock(
            return_value=iter([]))

        result = self.nc.fw_policy_get_all()

        self.assertEqual([], result)

    def test_fip_get_all_404_returns_empty(self):
        """Test that 404 errors return empty list."""
        self.nc.conn.network.ips = mock.Mock(
            side_effect=os_exc.HttpException(http_status=404))

        result = self.nc.fip_get_all()

        self.assertEqual([], result)

    def test_fip_get_all_other_http_error_returns_empty(self):
        """Test that other HTTP errors return empty list."""
        self.nc.conn.network.ips = mock.Mock(side_effect=os_exc.HttpException(
            http_status=500))

        result = self.nc.fip_get_all()

        self.assertEqual([], result)

    def test_fip_get_all_non_http_exception_raises(self):
        """Test that non-HTTP exceptions are re-raised."""
        self.nc.conn.network.ips = mock.Mock(side_effect=RuntimeError(
            "Connection failed"))

        self.assertRaises(RuntimeError, self.nc.fip_get_all)
