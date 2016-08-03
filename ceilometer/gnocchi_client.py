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

from gnocchiclient import client
from gnocchiclient import exceptions as gnocchi_exc
from keystoneauth1 import session as ka_session
from oslo_config import cfg
from oslo_log import log
import requests

from ceilometer import keystone_client

LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('url',
               deprecated_for_removal=True,
               help='URL to Gnocchi. default: autodetection'),
]

cfg.CONF.register_opts(OPTS, group="dispatcher_gnocchi")


def get_gnocchiclient(conf, endpoint_override=None):
    requests_session = requests.session()
    for scheme in list(requests_session.adapters.keys()):
        requests_session.mount(scheme, ka_session.TCPKeepAliveAdapter(
            pool_block=True))

    session = keystone_client.get_session(requests_session=requests_session)
    return client.Client('1', session,
                         interface=conf.service_credentials.interface,
                         region_name=conf.service_credentials.region_name,
                         endpoint_override=endpoint_override)


# NOTE(sileht): This is the initial resource types created in Gnocchi
# This list must never change to keep in sync with what Gnocchi early
# database contents was containing
resources_initial = {
    "image": {
        "name": {"type": "string", "min_length": 0, "max_length": 255,
                 "required": True},
        "container_format": {"type": "string", "min_length": 0,
                             "max_length": 255, "required": True},
        "disk_format": {"type": "string", "min_length": 0, "max_length": 255,
                        "required": True},
    },
    "instance": {
        "flavor_id": {"type": "string", "min_length": 0, "max_length": 255,
                      "required": True},
        "image_ref": {"type": "string", "min_length": 0, "max_length": 255,
                      "required": False},
        "host": {"type": "string", "min_length": 0, "max_length": 255,
                 "required": True},
        "display_name": {"type": "string", "min_length": 0, "max_length": 255,
                         "required": True},
        "server_group": {"type": "string", "min_length": 0, "max_length": 255,
                         "required": False},
    },
    "instance_disk": {
        "name": {"type": "string", "min_length": 0, "max_length": 255,
                 "required": True},
        "instance_id": {"type": "uuid", "required": True},
    },
    "instance_network_interface": {
        "name": {"type": "string", "min_length": 0, "max_length": 255,
                 "required": True},
        "instance_id": {"type": "uuid", "required": True},
    },
    "volume": {
        "display_name": {"type": "string", "min_length": 0, "max_length": 255,
                         "required": False},
    },
    "swift_account": {},
    "ceph_account": {},
    "network": {},
    "identity": {},
    "ipmi": {},
    "stack": {},
    "host": {
        "host_name": {"type": "string", "min_length": 0, "max_length": 255,
                      "required": True},
    },
    "host_network_interface": {
        "host_name": {"type": "string", "min_length": 0, "max_length": 255,
                      "required": True},
        "device_name": {"type": "string", "min_length": 0, "max_length": 255,
                        "required": False},
    },
    "host_disk": {
        "host_name": {"type": "string", "min_length": 0, "max_length": 255,
                      "required": True},
        "device_name": {"type": "string", "min_length": 0, "max_length": 255,
                        "required": False},
    },
}


def upgrade_resource_types(conf):
    gnocchi = get_gnocchiclient(conf)
    # TODO(sileht): Detect what is the version of the schema created
    # in Gnocchi, we don't have local database to store this.
    # For now we can upgrade the schema so we are safe :p
    for name, attributes in resources_initial.items():
        try:
            gnocchi.resource_type.get(name=name)
        except gnocchi_exc.NotFound:
            # FIXME(sileht): It should be ResourceTypeNotFound but
            # gnocchiclient doesn't raise that :(
            rt = {'name': name, 'attributes': attributes}
            try:
                gnocchi.resource_type.create(resource_type=rt)
            except Exception:
                LOG.error("Gnocchi resource creation fail", exc_info=True)
        else:
            # NOTE(sileht): We have to handle this case when it will be
            # possible to add/rm resource-types columns
            pass
