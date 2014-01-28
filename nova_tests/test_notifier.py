# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Julien Danjou <julien@danjou.info>
#         Doug Hellmann <doug.hellmann@dreamhost.com>
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

import contextlib
import datetime

import mock

from stevedore import extension

## NOTE(dhellmann): These imports are not in the generally approved
## alphabetical order, but they are in the order that actually
## works. Please don't change them.
from nova.tests import fake_network
from nova.compute import vm_states
try:
    from nova.compute import flavors
except ImportError:
    from nova.compute import instance_types as flavors

from nova.objects import instance as nova_instance
from nova import config
from nova import context
from nova import db
from nova.openstack.common import importutils
from nova.openstack.common import log as logging

# This option is used in the nova_notifier module, so make
# sure it is defined.
config.cfg.CONF.import_opt('compute_manager', 'nova.service')

# HACK(jd) Import this first because of the second HACK below, and because
# of Nova not having these module yet as of this writing
from ceilometer.openstack.common import test
from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common.fixture import moxstubout

# HACK(dhellmann): Import this before any other ceilometer code
# because the notifier module messes with the import path to force
# nova's version of oslo to be used instead of ceilometer's.
from ceilometer.compute import nova_notifier

from ceilometer import sample
from ceilometer.compute.pollsters import util

LOG = logging.getLogger(__name__)
nova_CONF = config.cfg.CONF


class TestNovaNotifier(test.BaseTestCase):

    class Pollster(object):
        instances = []
        test_data_1 = sample.Sample(
            name='test1',
            type=sample.TYPE_CUMULATIVE,
            unit='units-go-here',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'Pollster',
                               },
        )

        def get_samples(self, manager, cache, instance):
            self.instances.append((manager, instance))
            test_data_2 = util.make_sample_from_instance(
                instance,
                name='test2',
                type=sample.TYPE_CUMULATIVE,
                unit='units-go-here',
                volume=1,
            )
            return [self.test_data_1, test_data_2]

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestNovaNotifier, self).setUp()
        nova_CONF.compute_driver = 'nova.virt.fake.FakeDriver'
        nova_CONF.notification_driver = [
            nova_notifier.__name__,
            'nova.openstack.common.notifier.rpc_notifier',
        ]
        nova_CONF.rpc_backend = 'nova.openstack.common.rpc.impl_fake'
        nova_CONF.vnc_enabled = False
        nova_CONF.spice.enabled = False
        self.compute = importutils.import_object(nova_CONF.compute_manager)
        self.context = context.get_admin_context()
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs
        fake_network.set_stub_network_methods(self.stubs)

        self.instance_data = {"display_name": "instance-1",
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
                              'node': "fakenode",
                              "host": "fakehost",
                              "availability_zone":
                              "1e3ce043029547f1a61c1996d1a531a4",
                              "created_at": '2012-05-08 20:23:41',
                              "launched_at": '2012-05-08 20:25:45',
                              "terminated_at": '2012-05-09 20:23:41',
                              "os_type": "linux",
                              "kernel_id": "kernelid",
                              "ramdisk_id": "ramdiskid",
                              "vm_state": vm_states.ACTIVE,
                              "task_state": None,
                              "access_ip_v4": "192.168.5.4",
                              "access_ip_v6": "2001:DB8::0",
                              "metadata": {},
                              "uuid": "144e08f4-00cb-11e2-888e-5453ed1bbb5f",
                              "system_metadata": {},
                              "user_data": None,
                              "cleaned": 0,
                              "deleted": None,
                              "vm_mode": None,
                              "deleted_at": None,
                              "disable_terminate": False,
                              "root_device_name": None,
                              "default_swap_device": None,
                              "launched_on": None,
                              "display_description": None,
                              "key_data": None,
                              "key_name": None,
                              "config_drive": None,
                              "power_state": None,
                              "default_ephemeral_device": None,
                              "progress": 0,
                              "scheduled_at": None,
                              "updated_at": None,
                              "shutdown_terminate": False,
                              "cell_name": 'cell',
                              "locked": False,
                              "locked_by": None,
                              "launch_index": 0,
                              "auto_disk_config": False,
                              "ephemeral_key_uuid": None
                              }

        self.instance = nova_instance.Instance()
        self.instance = nova_instance.Instance._from_db_object(
                context, self.instance, self.instance_data,
                expected_attrs=['metadata', 'system_metadata'])

        self.stubs.Set(db, 'instance_info_cache_delete', self.do_nothing)
        self.stubs.Set(db, 'instance_destroy', self.do_nothing)
        self.stubs.Set(db, 'instance_system_metadata_get',
                       self.fake_db_instance_system_metadata_get)
        self.stubs.Set(db, 'block_device_mapping_get_all_by_instance',
                       lambda context, instance: {})
        self.stubs.Set(db, 'instance_update_and_get_original',
                       lambda *args, **kwargs: (self.instance, self.instance))
        self.stubs.Set(flavors, 'extract_flavor', self.fake_extract_flavor)

        # Set up to capture the notification messages generated by the
        # plugin and to invoke our notifier plugin.
        self.notifications = []

        ext_mgr = extension.ExtensionManager.make_test_instance(
            extensions=[
                extension.Extension('test',
                                    None,
                                    None,
                                    self.Pollster(),
                                ),
            ],
        )
        self.ext_mgr = ext_mgr
        self.gatherer = nova_notifier.DeletedInstanceStatsGatherer(ext_mgr)
        # Initialize the global _gatherer in nova_notifier to use the
        # gatherer in this test instead of the gatherer in nova_notifier.
        nova_notifier.initialize_gatherer(self.gatherer)

        # Terminate the instance to trigger the notification.
        with contextlib.nested(
            # Under Grizzly, Nova has moved to no-db access on the
            # compute node. The compute manager uses RPC to talk to
            # the conductor. We need to disable communication between
            # the nova manager and the remote system since we can't
            # expect the message bus to be available, or the remote
            # controller to be there if the message bus is online.
            mock.patch.object(self.compute, 'conductor_api'),
            # The code that looks up the instance uses a global
            # reference to the API, so we also have to patch that to
            # return our fake data.
            mock.patch.object(nova_notifier.conductor_api,
                              'instance_get_by_uuid',
                              self.fake_instance_ref_get),
            mock.patch('nova.openstack.common.notifier.rpc_notifier.notify',
                       self.notify)
        ):
            with mock.patch.object(self.compute.conductor_api,
                                   'instance_destroy',
                                   return_value=self.instance):
                self.compute.terminate_instance(self.context,
                                                instance=self.instance,
                                                bdms=[],
                                                reservations=[])

    def tearDown(self):
        self.Pollster.instances = []
        super(TestNovaNotifier, self).tearDown()
        nova_notifier._gatherer = None

    # The instance returned by conductor API is a dictionary actually,
    # and it will be transformed to an nova_notifier.Instance object
    # that looks like what the novaclient gives them.
    def fake_instance_ref_get(self, context, id_):
        return self.instance_data

    @staticmethod
    def fake_extract_flavor(instance_ref):
        return {'ephemeral_gb': 0,
                'flavorid': '1',
                'id': 2,
                'memory_mb': 512,
                'name': 'm1.tiny',
                'root_gb': 1,
                'rxtx_factor': 1.0,
                'swap': 0,
                'vcpu_weight': None,
                'vcpus': 1}

    @staticmethod
    def do_nothing(*args, **kwargs):
        pass

    @staticmethod
    def fake_db_instance_system_metadata_get(context, uuid):
        return dict(meta_a=123, meta_b="foobar")

    def notify(self, context, message):
        self.notifications.append(message)

    def test_pollster_called(self):
        self.assertEqual(len(self.Pollster.instances), 1)

    def test_correct_instance(self):
        for i, (gatherer, inst) in enumerate(self.Pollster.instances):
            self.assertEqual((i, inst.uuid), (i, self.instance.uuid))

    def test_correct_gatherer(self):
        for i, (gatherer, inst) in enumerate(self.Pollster.instances):
            self.assertEqual((i, gatherer), (i, self.gatherer))

    def test_instance_flavor(self):
        inst = nova_notifier.Instance(context, self.instance)
        self.assertEqual(inst.flavor['name'], 'm1.tiny')
        self.assertEqual(inst.flavor['flavor_id'], '1')

    def test_samples(self):
        # Ensure that the outgoing notification looks like what we expect
        for message in self.notifications:
            event = message['event_type']
            if event != 'compute.instance.delete.samples':
                continue
            payload = message['payload']
            samples = payload['samples']

            # Because the playload's samples doesn't include instance
            # metadata, we can't check the metadata field directly.
            # But if we make a mistake in the instance attributes, such
            # as missing instance.name or instance.flavor['name'], it
            # will raise AttributeError, which results the number of
            # the samples doesn't equal to 2.
            self.assertEqual(len(samples), 2)
            s1 = payload['samples'][0]
            self.assertEqual(s1, {'name': 'test1',
                                  'type': sample.TYPE_CUMULATIVE,
                                  'unit': 'units-go-here',
                                  'volume': 1,
                                  })
            s2 = payload['samples'][1]
            self.assertEqual(s2, {'name': 'test2',
                                  'type': sample.TYPE_CUMULATIVE,
                                  'unit': 'units-go-here',
                                  'volume': 1,
                                  })

            break
        else:
            assert False, 'Did not find expected event'
