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
from nova import manager
from nova import flags
import nova.virt.connection

# Import rabbit_notifier to register notification_topics flag
import nova.notifier.rabbit_notifier

from ceilometer import rpc

FLAGS = flags.FLAGS
# FIXME(dhellmann): We need to have the main program set up logging
# correctly so messages from modules outside of the nova package
# appear in the output.
LOG = logging.getLogger('nova.' + __name__)


class InstanceManager(manager.Manager):
    def init_host(self):
        self.connection = rpc.Connection(flags.FLAGS)
        self.connection.declare_topic_consumer(
            topic='%s.info' % flags.FLAGS.notification_topics[0],
            callback=self._on_notification)
        self.connection.consume_in_thread()

    def _on_notification(self, body):
        event_type = body.get('event_type')
        LOG.info('NOTIFICATION: %s', event_type)


class ComputeManager(manager.Manager):
    def _get_disks(self, conn, instance):
        """Get disks of an instance, only used to bypass bug#998089."""
        domain = conn._conn.lookupByName(instance)
        tree = etree.fromstring(domain.XMLDesc(0))
        return filter(bool,
                      [target.get('dev')
                       for target in tree.findall('devices/disk/target')
                       ])

    @manager.periodic_task
    def _fetch_diskio(self, context):
        if FLAGS.connection_type == 'libvirt':
            conn = nova.virt.connection.get_connection(read_only=True)
            for instance in self.db.instance_get_all_by_host(context,
                                                             self.host):
                # TODO(jd) This does not work see bug#998089
                # for disk in conn.get_disks(instance.name):
                try:
                    disks = self._get_disks(conn, instance.name)
                except Exception as err:
                    LOG.warning('Ignoring instance %s: %s', instance.name, err)
                    LOG.exception(err)
                    continue
                for disk in disks:
                    stats = conn.block_stats(instance.name, disk)
                    LOG.info("DISKIO USAGE: %s %s: read-requests=%d read-bytes=%d write-requests=%d write-bytes=%d errors=%d" % (instance, disk, stats[0], stats[1], stats[2], stats[3], stats[4]))

    @manager.periodic_task
    def _fetch_cputime(self, context):
        conn = nova.virt.connection.get_connection(read_only=True)
        for instance in self.db.instance_get_all_by_host(context, self.host):
            LOG.info("CPUTIME USAGE: %s %d" % (instance, conn.get_info(instance)['cpu_time']))
