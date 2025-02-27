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

from ceilometer.compute.virt.libvirt import utils as libvirt_utils
from ceilometer import nova_client
from ceilometer.polling import plugin_base

OPTS = [
    cfg.StrOpt('instance_discovery_method',
               default='libvirt_metadata',
               choices=[('naive', 'poll nova to get all instances'),
                        ('workload_partitioning',
                         'poll nova to get instances of the compute'),
                        ('libvirt_metadata',
                         'get instances from libvirt metadata but without '
                         'instance metadata (recommended)')],
               help="Ceilometer offers many methods to discover the instance "
                    "running on a compute node"),
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
                    "defined in pipeline. This option is only used "
                    "for agent polling to Nova API, so it will work only "
                    "when 'instance_discovery_method' is set to 'naive'."),
    cfg.IntOpt('resource_cache_expiry',
               default=3600,
               min=0,
               help="The expiry to totally refresh the instances resource "
                    "cache, since the instance may be migrated to another "
                    "host, we need to clean the legacy instances info in "
                    "local cache by totally refreshing the local cache. "
                    "The minimum should be the value of the config option "
                    "of resource_update_interval. This option is only used "
                    "for agent polling to Nova API, so it will work only "
                    "when 'instance_discovery_method' is set to 'naive'."),
    cfg.BoolOpt('fetch_extra_metadata',
                default=True,
                help="Whether or not additional instance attributes that "
                     "require Nova API queries should be fetched. Currently "
                     "the only value that requires fetching from Nova API is "
                     "'metadata', the attribute storing user-configured "
                     "server metadata, which is used to fill out some "
                     "optional fields such as the server group of an "
                     "instance. fetch_extra_metadata is currently set to "
                     "True by default, but to reduce the load on Nova API "
                     "this will be changed to False in a future release."),
]

LOG = log.getLogger(__name__)


class NovaLikeServer:
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
        super().__init__(conf)
        if not self.method:
            self.method = conf.compute.instance_discovery_method

        self.nova_cli = nova_client.Client(conf)
        self.expiration_time = conf.compute.resource_update_interval
        self.cache_expiry = conf.compute.resource_cache_expiry
        if self.method == "libvirt_metadata":
            # 4096 resources on a compute should be enough :)
            self._flavor_id_cache = cachetools.LRUCache(4096)
            self._server_cache = cachetools.LRUCache(4096)
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

    def _get_flavor_id(self, flavor_xml, instance_id):
        flavor_name = flavor_xml.attrib["name"]
        # Flavor ID is available in libvirt metadata from 2025.2 onwards.
        flavor_id = flavor_xml.attrib.get("id")
        if flavor_id:
            return flavor_id
        # If not found in libvirt metadata, fallback to API queries.
        # If we already have the server metadata get the flavor ID from there.
        if self.conf.compute.fetch_extra_metadata:
            server = self.get_server(instance_id)
            if server:
                return server.flavor["id"]
        # If server metadata is not otherwise fetched, or the query failed,
        # query just the flavor for better cache hit rates.
        return (self.get_flavor_id(flavor_name) or flavor_name)

    def _get_flavor_extra_specs(self, flavor_xml):
        # Extra specs are available in libvirt metadata from 2025.2 onwards.
        # Note that this checks for existence of the element, not whether
        # or not it is empty, as it *can* exist but have nothing set in it.
        extra_specs = flavor_xml.find("./extraSpecs")
        if extra_specs is not None:
            return {
                extra_spec.attrib["name"]: extra_spec.text
                for extra_spec in extra_specs.findall("./extraSpec")}
        # If not found in libvirt metadata, return None to signify
        # "not fetched", as we don't support performing additional
        # API queries just for the extra specs.
        return None

    @cachetools.cachedmethod(operator.attrgetter('_flavor_id_cache'))
    def get_flavor_id(self, name):
        LOG.debug("Querying metadata for flavor %s from Nova API", name)
        try:
            return self.nova_cli.nova_client.flavors.find(
                name=name,
                is_public=None).id
        except exceptions.NotFound:
            return None

    @cachetools.cachedmethod(operator.attrgetter('_server_cache'))
    def get_server(self, uuid):
        LOG.debug("Querying metadata for instance %s from Nova API", uuid)
        try:
            return self.nova_cli.nova_client.servers.get(uuid)
        except exceptions.NotFound:
            return None

    @libvirt_utils.retry_on_disconnect
    def discover_libvirt_polling(self, manager, param=None):
        instances = []
        for domain in self.connection.listAllDomains():
            instance_id = domain.UUIDString()
            xml_string = libvirt_utils.instance_metadata(domain)
            if xml_string is None:
                continue

            full_xml = etree.fromstring(domain.XMLDesc())
            os_type_xml = full_xml.find("./os/type")
            metadata_xml = etree.fromstring(xml_string)

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

                extra_specs = self._get_flavor_extra_specs(flavor_xml)

                flavor = {
                    "id": self._get_flavor_id(flavor_xml, instance_id),
                    "name": flavor_xml.attrib["name"],
                    "vcpus": self._safe_find_int(flavor_xml, "vcpus"),
                    "ram": self._safe_find_int(flavor_xml, "memory"),
                    "disk": self._safe_find_int(flavor_xml, "disk"),
                    "ephemeral": self._safe_find_int(flavor_xml, "ephemeral"),
                    "swap": self._safe_find_int(flavor_xml, "swap"),
                }
                if extra_specs is not None:
                    flavor["extra_specs"] = extra_specs

                image_xml = metadata_xml.find("./root[@type='image']")
                image = ({'id': image_xml.attrib['uuid']}
                         if image_xml is not None else None)

                image_meta_xml = metadata_xml.find("./image")
                if image_meta_xml is not None:
                    # If the <image> element exists at all, Nova supports
                    # image_meta in libvirt metadata. Add it to the instance
                    # attributes even if all the required values are empty.
                    image_meta = {}
                    base_image_ref = image_meta_xml.attrib.get("uuid")
                    if base_image_ref is not None:
                        image_meta["base_image_ref"] = base_image_ref
                    # The following properties get special treatment
                    # because they are set as such in SM_INHERITABLE_KEYS,
                    # as defined in nova/utils.py.
                    container_format_xml = image_meta_xml.find(
                        "./containerFormat")
                    if container_format_xml is not None:
                        image_meta["container_format"] = (
                            container_format_xml.text)
                    disk_format_xml = image_meta_xml.find("./diskFormat")
                    if disk_format_xml is not None:
                        image_meta["disk_format"] = disk_format_xml.text
                    min_disk_xml = image_meta_xml.find("./minDisk")
                    if min_disk_xml is not None:
                        image_meta["min_disk"] = min_disk_xml.text
                    min_ram_xml = image_meta_xml.find("./minRam")
                    if min_ram_xml is not None:
                        image_meta["min_ram"] = min_ram_xml.text
                    # Get additional properties defined in image_meta.
                    properties_xml = image_meta_xml.find("./properties")
                    if properties_xml is not None:
                        for prop in properties_xml.findall("./property"):
                            image_meta[prop.attrib["name"]] = prop.text
                else:
                    # None for "no image_meta found".
                    image_meta = None

                # Getting the server metadata requires expensive Nova API
                # queries, and may potentially contain sensitive user info,
                # so it is only fetched when configured to do so.
                if self.conf.compute.fetch_extra_metadata:
                    server = self.get_server(instance_id)
                    metadata = server.metadata if server is not None else {}
                else:
                    metadata = {}
            except AttributeError:
                LOG.error(
                    "Fail to get domain uuid %s metadata: "
                    "metadata was missing expected attributes",
                    instance_id)
                continue

            dom_state = domain.state()[0]
            vm_state = libvirt_utils.LIBVIRT_POWER_STATE.get(dom_state)
            status = libvirt_utils.LIBVIRT_STATUS.get(dom_state)

            # From:
            # https://github.com/openstack/nova/blob/852f40fd0c6e9d8878212ff3120556668023f1c4/nova/api/openstack/compute/views/servers.py#L214-L220
            host_id = hashlib.sha224(
                (project_id + self.conf.host).encode('utf-8')).hexdigest()

            instance_data = {
                "id": instance_id,
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
                "metadata": metadata,
                # "OS-EXT-STS:task_state"
                # 'reservation_id',
                # 'OS-EXT-AZ:availability_zone',
                # 'kernel_id',
                # 'ramdisk_id',
                # some image detail
            }
            if image_meta is not None:
                instance_data["image_meta"] = image_meta

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
