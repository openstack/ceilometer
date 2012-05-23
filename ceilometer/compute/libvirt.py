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

from lxml import etree

from nova import log as logging
from nova import flags
import nova.virt.connection

from .. import counter
from .. import plugin


FLAGS = flags.FLAGS
# FIXME(dhellmann): We need to have the main program set up logging
# correctly so messages from modules outside of the nova package
# appear in the output.
LOG = logging.getLogger('nova.' + __name__)

MIB = 2 ** 20  # mebibytes


def make_counter_from_instance(instance, type, volume):
    return counter.Counter(
        source='?',
        type=type,
        volume=volume,
        user_id=instance.user_id,
        project_id=instance.project_id,
        resource_id=instance.uuid,
        datetime=None,
        duration=None,
        resource_metadata={
            'display_name': instance.display_name,
            'instance_type': instance.instance_type.flavorid,
            'host': instance.host,
            },
        )


class DiskIOPollster(plugin.PollsterBase):

    LOG = logging.getLogger('nova.' + __name__ + '.diskio')

    def _get_disks(self, conn, instance):
        """Get disks of an instance, only used to bypass bug#998089."""
        domain = conn._conn.lookupByName(instance)
        tree = etree.fromstring(domain.XMLDesc(0))
        return filter(bool,
                      [target.get('dev')
                       for target in tree.findall('devices/disk/target')
                       ])

    def get_counters(self, manager, context):
        if FLAGS.connection_type == 'libvirt':
            conn = nova.virt.connection.get_connection(read_only=True)
            for instance in manager.db.instance_get_all_by_host(context,
                                                                manager.host):
                # TODO(jd) This does not work see bug#998089
                # for disk in conn.get_disks(instance.name):
                try:
                    disks = self._get_disks(conn, instance.name)
                except Exception as err:
                    self.LOG.warning('Ignoring instance %s: %s', instance.name, err)
                    self.LOG.exception(err)
                    continue
                bytes = 0
                for disk in disks:
                    stats = conn.block_stats(instance.name, disk)
                    self.LOG.info("DISKIO USAGE: %s %s: read-requests=%d read-bytes=%d write-requests=%d write-bytes=%d errors=%d",
                             instance, disk, stats[0], stats[1], stats[2], stats[3], stats[4])
                    bytes += stats[1] + stats[3]  # combine read and write
                yield make_counter_from_instance(instance,
                                                 type='disk',
                                                 volume=bytes / MIB,
                                                 )


class CPUPollster(plugin.PollsterBase):

    LOG = logging.getLogger('nova.' + __name__ + '.cpu')

    def get_counters(self, manager, context):
        conn = nova.virt.connection.get_connection(read_only=True)
        # FIXME(dhellmann): How do we get a list of instances without
        # talking directly to the database?
        for instance in manager.db.instance_get_all_by_host(context, manager.host):
            self.LOG.info('checking instance %s', instance.uuid)
            try:
                cpu_info = conn.get_info(instance)
                self.LOG.info("CPUTIME USAGE: %s %d", instance, cpu_info['cpu_time'])
                yield make_counter_from_instance(instance,
                                                 type='cpu',
                                                 volume=cpu_info['cpu_time'],
                                                 )
            except Exception as err:
                self.LOG.error('could not get CPU time for %s: %s',
                               instance.uuid, err)
                self.LOG.exception(err)
