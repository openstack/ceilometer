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

from openstack import connection
from oslo_config import cfg

from ceilometer import keystone_client


SERVICE_OPTS = [
    cfg.StrOpt('cinder',
               default='block-storage',
               help='Cinder service type.'),
]


class Client:
    def __init__(self, conf):
        creds = conf.service_credentials
        # NOTE(mnederlof): We set 3.64 (the maximum for Wallaby) because:
        # we need at least 3.41 to get user_id on snapshots.
        # we need at least 3.56 for user_id and project_id on backups.
        # we need at least 3.63 for volume_type_id on volumes.
        self._conn = connection.Connection(
            block_storage_api_version='3.64',
            session=keystone_client.get_session(conf),
            oslo_conf=conf,
            region_name=creds.region_name,
            block_storage_interface=creds.interface,
            service_types={conf.service_types.cinder}
        )

    def list_volumes(self, search_opts=None):
        search_opts = dict(search_opts or {})
        all_projects = search_opts.pop('all_projects', True)
        return list(
            self._conn.block_storage.volumes(
                details=True,
                all_projects=all_projects,
                **search_opts))

    def list_volume_snapshots(self, search_opts=None):
        search_opts = dict(search_opts or {})
        all_projects = search_opts.pop('all_projects', True)
        return list(
            self._conn.block_storage.snapshots(
                details=True,
                all_projects=all_projects,
                **search_opts))

    def list_backups(self, search_opts=None):
        search_opts = dict(search_opts or {})
        all_projects = search_opts.pop('all_projects', True)
        return list(
            self._conn.block_storage.backups(
                details=True,
                all_projects=all_projects,
                **search_opts))

    def list_pools(self):
        # openstacksdk hardcodes detail=True in the Pools resource URL, so
        # detailed capacity data is always returned.
        return list(self._conn.block_storage.backend_pools())

    def list_services(self):
        return list(self._conn.block_storage.services())
