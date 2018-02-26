#
# Copyright 2014 Red Hat, Inc
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

import hashlib
from lxml import etree
import operator
import threading

import cachetools
from novaclient import exceptions
from oslo_config import cfg
from oslo_log import log
from oslo_utils import timeutils


try:
    import libvirt
except ImportError:
    libvirt = None

from ceilometer.agent import plugin_base
from ceilometer.compute.virt.libvirt import utils as libvirt_utils
from ceilometer import nova_client

OPTS = [
    cfg.BoolOpt('workload_partitioning',
                default=False,
                deprecated_for_removal=True,
                help='Enable work-load partitioning, allowing multiple '
                     'compute agents to be run simultaneously. '
                     '(replaced by instance_discovery_method)'),
    cfg.StrOpt('instance_discovery_method',
               default='libvirt_metadata',
               choices=['naive', 'workload_partitioning', 'libvirt_metadata'],
               help="Ceilometer offers many methods to discover the instance "
                    "running on a compute node: \n"
                    "* naive: poll nova to get all instances\n"
                    "* workload_partitioning: poll nova to get instances of "
                    "the compute\n"
                    "* libvirt_metadata: get instances from libvirt metadata "
                    "  but without instance metadata (recommended for Gnocchi "
                    "  backend"),
    cfg.IntOpt('resource_update_interval',
               default=0,
               min=0,
               help="New instances will be discovered periodically based"
                    " on this option (in seconds). By default, "
                    "the agent discovers instances according to pipeline "
                    "polling interval. If option is greater than 0, "
                    "the instance list to poll will be updated based "
                    "on this option's interval. Measurements relating "
                    "to the instances will match intervals "
                    "defined in pipeline. "),
    cfg.IntOpt('resource_cache_expiry',
               default=3600,
               min=0,
               help="The expiry to totally refresh the instances resource "
                    "cache, since the instance may be migrated to another "
                    "host, we need to clean the legacy instances info in "
                    "local cache by totally refreshing the local cache. "
                    "The minimum should be the value of the config option "
                    "of resource_update_interval. This option is only used "
                    "for agent polling to Nova API, so it will works only "
                    "when 'instance_discovery_method' was set to 'naive'.")
]

LOG = log.getLogger(__name__)


class NovaLikeServer(object):
    def __init__(self, **kwargs):
        self.id = kwargs.pop('id')
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return '<NovaLikeServer: %s>' % getattr(self, 'name', 'unknown-name')

    def __eq__(self, other):
        return self.id == other.id


class InstanceDiscovery(plugin_base.DiscoveryBase):
    method = None

    def __init__(self, conf):
        super(InstanceDiscovery, self).__init__(conf)
        if not self.method:
            self.method = conf.compute.instance_discovery_method

            # For backward compatibility
            if self.method == "naive" and conf.compute.workload_partitioning:
                self.method = "workload_partitioning"

        self.nova_cli = nova_client.Client(conf)
        self.expiration_time = conf.compute.resource_update_interval
        self.cache_expiry = conf.compute.resource_cache_expiry
        if self.method == "libvirt_metadata":
            # 4096 instances on a compute should be enough :)
            self._flavor_cache = cachetools.LRUCache(4096)
        else:
            self.lock = threading.Lock()
            self.instances = {}
            self.last_run = None
            self.last_cache_expire = None

    @property
    def connection(self):
        return libvirt_utils.refresh_libvirt_connection(self.conf, self)

    def discover(self, manager, param=None):
        """Discover resources to monitor."""
        if self.method != "libvirt_metadata":
            return self.discover_nova_polling(manager, param=None)
        else:
            return self.discover_libvirt_polling(manager, param=None)

    @staticmethod
    def _safe_find_int(xml, path):
        elem = xml.find("./%s" % path)
        if elem is not None:
            return int(elem.text)
        return 0

    @cachetools.cachedmethod(operator.attrgetter('_flavor_cache'))
    def get_flavor_id(self, name):
        try:
            return self.nova_cli.nova_client.flavors.find(name=name).id
        except exceptions.NotFound:
            return None

    @libvirt_utils.retry_on_disconnect
    def discover_libvirt_polling(self, manager, param=None):
        instances = []
        for domain in self.connection.listAllDomains():
            try:
                xml_string = domain.metadata(
                    libvirt.VIR_DOMAIN_METADATA_ELEMENT,
                    "http://openstack.org/xmlns/libvirt/nova/1.0")
            except libvirt.libvirtError as e:
                if libvirt_utils.is_disconnection_exception(e):
                    # Re-raise the exception so it's handled and retries
                    raise
                LOG.error(
                    "Fail to get domain uuid %s metadata, libvirtError: %s",
                    domain.UUIDString(), e.message)
                continue

            full_xml = etree.fromstring(domain.XMLDesc())
            os_type_xml = full_xml.find("./os/type")
            metadata_xml = etree.fromstring(xml_string)

            # TODO(sileht): We don't have the flavor ID here So the Gnocchi
            # resource update will fail for compute sample (or put None ?)
            # We currently poll nova to get the flavor ID, but storing the
            # flavor_id doesn't have any sense because the flavor description
            # can change over the time, we should store the detail of the
            # flavor. this is why nova doesn't put the id in the libvirt
            # metadata

            try:
                flavor_xml = metadata_xml.find(
                    "./flavor")
                user_id = metadata_xml.find(
                    "./owner/user").attrib["uuid"]
                project_id = metadata_xml.find(
                    "./owner/project").attrib["uuid"]
                instance_name = metadata_xml.find(
                    "./name").text
                instance_arch = os_type_xml.attrib["arch"]

                flavor = {
                    "id": self.get_flavor_id(flavor_xml.attrib["name"]),
                    "name": flavor_xml.attrib["name"],
                    "vcpus": self._safe_find_int(flavor_xml, "vcpus"),
                    "ram": self._safe_find_int(flavor_xml, "memory"),
                    "disk": self._safe_find_int(flavor_xml, "disk"),
                    "ephemeral": self._safe_find_int(flavor_xml, "ephemeral"),
                    "swap": self._safe_find_int(flavor_xml, "swap"),
                }

                # The image description is partial, but Gnocchi only care about
                # the id, so we are fine
                image_xml = metadata_xml.find("./root[@type='image']")
                image = ({'id': image_xml.attrib['uuid']}
                         if image_xml is not None else None)
            except AttributeError as e:
                LOG.error(
                    "Fail to get domain uuid %s metadata: "
                    "metadata was missing expected attributes",
                    domain.UUIDString())
                continue

            dom_state = domain.state()[0]
            vm_state = libvirt_utils.LIBVIRT_POWER_STATE.get(dom_state)
            status = libvirt_utils.LIBVIRT_STATUS.get(dom_state)

            # From:
            # https://github.com/openstack/nova/blob/852f40fd0c6e9d8878212ff3120556668023f1c4/nova/api/openstack/compute/views/servers.py#L214-L220
            host_id = hashlib.sha224(
                (project_id + self.conf.host).encode('utf-8')).hexdigest()

            instance_data = {
                "id": domain.UUIDString(),
                "name": instance_name,
                "flavor": flavor,
                "image": image,
                "os_type": os_type_xml.text,
                "architecture": instance_arch,

                "OS-EXT-SRV-ATTR:instance_name": domain.name(),
                "OS-EXT-SRV-ATTR:host": self.conf.host,
                "OS-EXT-STS:vm_state": vm_state,

                "tenant_id": project_id,
                "user_id": user_id,

                "hostId": host_id,
                "status": status,

                # NOTE(sileht): Other fields that Ceilometer tracks
                # where we can't get the value here, but their are
                # retrieved by notification
                "metadata": {},
                # "OS-EXT-STS:task_state"
                # 'reservation_id',
                # 'OS-EXT-AZ:availability_zone',
                # 'kernel_id',
                # 'ramdisk_id',
                # some image detail
            }

            LOG.debug("instance data: %s", instance_data)
            instances.append(NovaLikeServer(**instance_data))
        return instances

    def discover_nova_polling(self, manager, param=None):
        secs_from_last_update = 0
        utc_now = timeutils.utcnow(True)
        secs_from_last_expire = 0
        if self.last_run:
            secs_from_last_update = timeutils.delta_seconds(
                self.last_run, utc_now)
        if self.last_cache_expire:
            secs_from_last_expire = timeutils.delta_seconds(
                self.last_cache_expire, utc_now)

        instances = []
        # NOTE(ityaptin) we update make a nova request only if
        # it's a first discovery or resources expired
        with self.lock:
            if (not self.last_run or secs_from_last_update >=
                    self.expiration_time):
                try:
                    if (secs_from_last_expire < self.cache_expiry and
                            self.last_run):
                        since = self.last_run.isoformat()
                    else:
                        since = None
                        self.instances.clear()
                        self.last_cache_expire = utc_now
                    instances = self.nova_cli.instance_get_all_by_host(
                        self.conf.host, since)
                    self.last_run = utc_now
                except Exception:
                    # NOTE(zqfan): instance_get_all_by_host is wrapped and will
                    # log exception when there is any error. It is no need to
                    #  raise it again and print one more time.
                    return []

            for instance in instances:
                if getattr(instance, 'OS-EXT-STS:vm_state', None) in [
                   'deleted', 'error']:
                    self.instances.pop(instance.id, None)
                else:
                    self.instances[instance.id] = instance

        return self.instances.values()

    @property
    def group_id(self):
        return self.conf.host
