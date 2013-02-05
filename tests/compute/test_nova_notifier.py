# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
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
"""Tests for ceilometer.compute.nova_notifier
"""

import mock
import datetime

from stevedore import extension
from stevedore.tests import manager as test_manager
from ceilometer.compute import manager

try:
    from nova import config
    nova_CONF = config.cfg.CONF
except ImportError:
    # XXX Folsom compat
    from nova import flags
    nova_CONF = flags.FLAGS
from nova import db
from nova import context
from nova import service  # For nova_CONF.compute_manager
from nova.tests import fake_network
from nova.compute import vm_states
# Needed for flags option, but Essex does not have it
try:
    from nova.openstack.common.notifier import api as notifier_api
except ImportError:
    notifier_api = None


from ceilometer import publish
from ceilometer import counter
from ceilometer.tests import base
from ceilometer.tests import skip
from ceilometer.compute import nova_notifier
from ceilometer.openstack.common import importutils


class TestNovaNotifier(base.TestCase):

    class Pollster(object):
        counters = []
        test_data = counter.Counter(
            name='test',
            type=counter.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'Pollster',
                               },
        )

        def get_counters(self, manager, instance):
            self.counters.append((manager, instance))
            return [self.test_data]

    def fake_db_instance_get(self, context, id_):
        if self.instance['uuid'] == id_:
            return mock.MagicMock(name=self.instance['name'],
                                  id=self.instance['uuid'])

    @staticmethod
    def do_nothing(*args, **kwargs):
        pass

    @staticmethod
    def fake_db_instance_system_metadata_get(context, uuid):
        return dict(meta_a=123, meta_b="foobar")

    @skip.skip_unless(notifier_api, "Notifier API not found")
    def setUp(self):
        super(TestNovaNotifier, self).setUp()
        nova_CONF.compute_driver = 'nova.virt.fake.FakeDriver'
        nova_CONF.notification_driver = [nova_notifier.__name__]
        nova_CONF.rpc_backend = 'ceilometer.openstack.common.rpc.impl_fake'
        self.compute = importutils.import_object(nova_CONF.compute_manager)
        self.context = context.get_admin_context()
        fake_network.set_stub_network_methods(self.stubs)

        self.instance = {"name": "instance-1",
                         "id": 1,
                         "image_ref": "FAKE",
                         "user_id": "FAKE",
                         "project_id": "FAKE",
                         "display_name": "FAKE NAME",
                         "hostname": "abcdef",
                         "reservation_id": "FAKE RID",
                         "instance_type_id": 1,
                         "architecture": "x86",
                         "memory_mb": "1024",
                         "root_gb": "20",
                         "ephemeral_gb": "0",
                         "vcpus": 1,
                         "host": "fakehost",
                         "availability_zone":
                         "1e3ce043029547f1a61c1996d1a531a4",
                         "created_at": '2012-05-08 20:23:41',
                         "os_type": "linux",
                         "kernel_id": "kernelid",
                         "ramdisk_id": "ramdiskid",
                         "vm_state": vm_states.ACTIVE,
                         "access_ip_v4": "someip",
                         "access_ip_v6": "someip",
                         "metadata": {},
                         "uuid": "144e08f4-00cb-11e2-888e-5453ed1bbb5f",
                         "system_metadata": {}}
        self.stubs.Set(db, 'instance_info_cache_delete', self.do_nothing)
        self.stubs.Set(db, 'instance_destroy', self.do_nothing)
        self.stubs.Set(db, 'instance_system_metadata_get',
                       self.fake_db_instance_system_metadata_get)
        self.stubs.Set(db, 'block_device_mapping_get_all_by_instance',
                       lambda context, instance: {})
        self.stubs.Set(db, 'instance_update_and_get_original',
                       lambda context, uuid, kwargs: (self.instance,
                                                      self.instance))

        self.stubs.Set(publish, 'publish_counter', self.do_nothing)
        agent_manager = manager.AgentManager()
        agent_manager.ext_manager = \
            test_manager.TestExtensionManager([
                extension.Extension('test',
                                    None,
                                    None,
                                    self.Pollster(),
                                    ),
            ])
        nova_notifier.initialize_manager(agent_manager)

    def tearDown(self):
        self.Pollster.counters = []
        super(TestNovaNotifier, self).tearDown()
        nova_notifier._agent_manager = None

    def test_notifications(self):
        # Folsom compatibility check
        try:
            import nova.conductor.api
        except ImportError:
            # Folsom does not have nova.conductor, and it is safe to
            # call this method directly, but not safe to mock it
            # because mock.patch() fails to find the original.
            self.stubs.Set(db, 'instance_get_by_uuid',
                           self.fake_db_instance_get)
            self.compute.terminate_instance(self.context,
                                            instance=self.instance)
        else:
            # Under Grizzly, Nova has moved to no-db access on the
            # compute node. The compute manager uses RPC to talk to
            # the conductor. We need to disable communication between
            # the nova manager and the remote system since we can't
            # expect the message bus to be available, or the remote
            # controller to be there if the message bus is online.
            @mock.patch.object(self.compute, 'conductor_api')
            # The code that looks up the instance uses a global
            # reference to the API, so we also have to patch that to
            # return our fake data.
            @mock.patch.object(nova.conductor.api.API,
                               'instance_get_by_uuid',
                               self.fake_db_instance_get)
            def run_test(*omit_args):
                self.compute.terminate_instance(self.context,
                                                instance=self.instance)

            run_test()

        self.assertTrue(self.Pollster.counters)
        self.assertTrue(self.Pollster.counters[0])
        self.assertEqual(self.Pollster.counters[0][0],
                         nova_notifier._agent_manager)
        self.assertEqual(self.Pollster.counters[0][1].id,
                         self.instance['uuid'])
        self.assertEqual(len(self.Pollster.counters), 1)
