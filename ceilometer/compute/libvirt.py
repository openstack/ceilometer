# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
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

import copy

from lxml import etree

from nova import flags

from ceilometer import counter
from ceilometer.compute import plugin
from ceilometer.compute import instance as compute_instance
from ceilometer.openstack.common import importutils
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils

FLAGS = flags.FLAGS


def get_libvirt_connection():
    """Return an open connection for talking to libvirt."""
    # The direct-import implementation only works with Folsom because
    # the configuration setting changed.
    try:
        return importutils.import_object_ns('nova.virt',
                                            FLAGS.compute_driver)
    except ImportError:
        # Fall back to the way it was done in Essex.
        import nova.virt.connection
        return nova.virt.connection.get_connection(read_only=True)


def make_counter_from_instance(instance, name, type, volume):
    return counter.Counter(
        source='?',
        name=name,
        type=type,
        volume=volume,
        user_id=instance.user_id,
        project_id=instance.project_id,
        resource_id=instance.uuid,
        timestamp=timeutils.isotime(),
        duration=None,
        resource_metadata=compute_instance.get_metadata_from_dbobject(
            instance),
        )


def make_vnic_counter(instance, name, type, volume, vnic_data):
    resource_metadata = copy.copy(vnic_data)
    resource_metadata['instance_id'] = instance.id

    return counter.Counter(
        source='?',
        name=name,
        type=type,
        volume=volume,
        user_id=instance.user_id,
        project_id=instance.project_id,
        resource_id=vnic_data['fref'],
        timestamp=timeutils.isotime(),
        duration=None,
        resource_metadata=resource_metadata
        )


class DiskIOPollster(plugin.ComputePollster):

    LOG = log.getLogger(__name__ + '.diskio')

    DISKIO_USAGE_MESSAGE = ' '.join(["DISKIO USAGE:",
                                     "%s %s:",
                                     "read-requests=%d",
                                     "read-bytes=%d",
                                     "write-requests=%d",
                                     "write-bytes=%d",
                                     "errors=%d",
                                     ])

    def _get_disks(self, conn, instance):
        """Get disks of an instance, only used to bypass bug#998089."""
        domain = conn._conn.lookupByName(instance)
        tree = etree.fromstring(domain.XMLDesc(0))
        return filter(bool,
                      [target.get('dev')
                       for target in tree.findall('devices/disk/target')
                       ])

    def get_counters(self, manager, instance):
        if FLAGS.compute_driver == 'libvirt.LibvirtDriver':
            conn = get_libvirt_connection()
            # TODO(jd) This does not work see bug#998089
            # for disk in conn.get_disks(instance.name):
            try:
                disks = self._get_disks(conn, instance.name)
            except Exception as err:
                self.LOG.warning('Ignoring instance %s: %s',
                                 instance.name, err)
                self.LOG.exception(err)
            else:
                bytes = 0
                requests = 0
                for disk in disks:
                    stats = conn.block_stats(instance.name, disk)
                    self.LOG.info(self.DISKIO_USAGE_MESSAGE,
                                  instance, disk, stats[0], stats[1],
                                  stats[2], stats[3], stats[4])
                    bytes += stats[1] + stats[3]  # combine read and write
                    requests += stats[0] + stats[2]
                yield make_counter_from_instance(instance,
                                                 name='disk.io.requests',
                                                 type=counter.TYPE_CUMULATIVE,
                                                 volume=requests,
                                                 )
                yield make_counter_from_instance(instance,
                                                 name='disk.io.bytes',
                                                 type=counter.TYPE_CUMULATIVE,
                                                 volume=bytes,
                                                 )


class CPUPollster(plugin.ComputePollster):

    LOG = log.getLogger(__name__ + '.cpu')

    def get_counters(self, manager, instance):
        conn = get_libvirt_connection()
        self.LOG.info('checking instance %s', instance.uuid)
        try:
            cpu_info = conn.get_info(instance)
            self.LOG.info("CPUTIME USAGE: %s %d",
                          instance, cpu_info['cpu_time'])
            yield make_counter_from_instance(instance,
                                             name='cpu',
                                             type=counter.TYPE_CUMULATIVE,
                                             volume=cpu_info['cpu_time'],
                                             )
            yield make_counter_from_instance(instance,
                                             name='instance',
                                             type=counter.TYPE_CUMULATIVE,
                                             volume=1,
                                             )
        except Exception as err:
            self.LOG.error('could not get CPU time for %s: %s',
                           instance.uuid, err)
            self.LOG.exception(err)


class NetPollster(plugin.ComputePollster):

    LOG = log.getLogger(__name__ + '.net')

    NET_USAGE_MESSAGE = ' '.join(["NETWORK USAGE:", "%s %s:", "read-bytes=%d",
                                  "write-bytes=%d"])

    def _get_vnics(self, conn, instance):
        """Get disks of an instance, only used to bypass bug#998089."""
        domain = conn._conn.lookupByName(instance.name)
        tree = etree.fromstring(domain.XMLDesc(0))
        vnics = []
        for interface in tree.findall('devices/interface'):
            vnic = {}
            vnic['name'] = interface.find('target').get('dev')
            vnic['mac'] = interface.find('mac').get('address')
            vnic['fref'] = interface.find('filterref').get('filter')
            for param in interface.findall('filterref/parameter'):
                vnic[param.get('name').lower()] = param.get('value')
            vnics.append(vnic)
        return vnics

    def get_counters(self, manager, instance):
        conn = get_libvirt_connection()
        self.LOG.info('checking instance %s', instance.uuid)
        try:
            vnics = self._get_vnics(conn, instance)
        except Exception as err:
            self.LOG.warning('Ignoring instance %s: %s',
                             instance.name, err)
            self.LOG.exception(err)
        else:
            domain = conn._conn.lookupByName(instance.name)
            for vnic in vnics:
                rx, _, _, _, tx, _, _, _ = domain.interfaceStats(vnic['name'])
                self.LOG.info(self.NET_USAGE_MESSAGE, instance.name,
                              vnic['name'], rx, tx)
                yield make_vnic_counter(instance,
                                        name='network.incoming.bytes',
                                        type=counter.TYPE_CUMULATIVE,
                                        volume=rx,
                                        vnic_data=vnic
                                       )
                yield make_vnic_counter(instance,
                                        name='network.outgoing.bytes',
                                        type=counter.TYPE_CUMULATIVE,
                                        volume=tx,
                                        vnic_data=vnic
                                       )
