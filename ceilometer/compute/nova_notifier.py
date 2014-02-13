# -*- encoding: utf-8 -*-
#
# Copyright © 2013 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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

import sys

from nova import notifications
from nova.openstack.common import log as logging
from nova.openstack.common.notifier import api as notifier_api

# HACK(dhellmann): Insert the nova version of openstack.common into
# sys.modules as though it was the copy from ceilometer, so that when
# we use modules from ceilometer below they do not re-define options.
# use the real ceilometer base package
import ceilometer  # noqa
for name in ['openstack', 'openstack.common', 'openstack.common.log']:
    sys.modules['ceilometer.' + name] = sys.modules['nova.' + name]

from nova.compute import flavors
from nova import conductor
from nova import utils

from stevedore import extension

from ceilometer.compute.virt import inspector
from ceilometer.openstack.common.gettextutils import _  # noqa


# This module runs inside the nova compute
# agent, which only configures the "nova" logger.
# We use a fake logger name in that namespace
# so that messages from this module appear
# in the log file.
LOG = logging.getLogger('nova.ceilometer.notifier')

_gatherer = None
conductor_api = conductor.API()


class DeletedInstanceStatsGatherer(object):

    def __init__(self, extensions):
        self.mgr = extensions
        self.inspector = inspector.get_hypervisor_inspector()

    def __call__(self, instance):
        cache = {}
        samples = self.mgr.map_method('get_samples',
                                      self,
                                      cache,
                                      instance)
        # samples is a list of lists, so flatten it before returning
        # the results
        results = []
        for slist in samples:
            results.extend(slist)
        return results


def initialize_gatherer(gatherer=None):
    """Set the callable used to gather stats for the instance.

    gatherer should be a callable accepting one argument (the instance
    ref), or None to have a default gatherer used
    """
    global _gatherer
    if gatherer is not None:
        LOG.debug(_('using provided stats gatherer %r'), gatherer)
        _gatherer = gatherer
    if _gatherer is None:
        LOG.debug(_('making a new stats gatherer'))
        mgr = extension.ExtensionManager(
            namespace='ceilometer.poll.compute',
            invoke_on_load=True,
        )
        _gatherer = DeletedInstanceStatsGatherer(mgr)
    return _gatherer


class Instance(object):
    """Model class for instances

    The pollsters all expect an instance that looks like what the
    novaclient gives them, but the conductor API gives us a
    dictionary. This class makes an object from the dictionary so we
    can pass it to the pollsters.
    """
    def __init__(self, context, info):
        for k, v in info.iteritems():
            if k == 'name':
                setattr(self, 'OS-EXT-SRV-ATTR:instance_name', v)
            elif k == 'metadata':
                setattr(self, k, utils.metadata_to_dict(v))
            else:
                setattr(self, k, v)

        instance_type = flavors.extract_flavor(info)
        self.flavor_name = instance_type.get('name', 'UNKNOWN')
        self.instance_flavor_id = instance_type.get('flavorid', '')
        LOG.debug(_('INFO %r'), info)

    @property
    def tenant_id(self):
        return self.project_id

    @property
    def flavor(self):
        return {
            'id': self.instance_type_id,
            'flavor_id': self.instance_flavor_id,
            'name': self.flavor_name,
            'vcpus': self.vcpus,
            'ram': self.memory_mb,
            'disk': self.root_gb + self.ephemeral_gb,
            'ephemeral': self.ephemeral_gb
        }

    @property
    def hostId(self):
        return self.host

    @property
    def image(self):
        return {'id': self.image_ref}

    @property
    def name(self):
        return self.display_name


def notify(context, message):
    if message['event_type'] != 'compute.instance.delete.start':
        LOG.debug(_('ignoring %s'), message['event_type'])
        return
    LOG.info(_('processing %s'), message['event_type'])
    gatherer = initialize_gatherer()

    instance_id = message['payload']['instance_id']
    LOG.debug(_('polling final stats for %r'), instance_id)

    # Ask for the instance details
    instance_ref = conductor_api.instance_get_by_uuid(
        context,
        instance_id,
    )

    # Get the default notification payload
    payload = notifications.info_from_instance(
        context, instance_ref, None, None)

    # Extend the payload with samples from our plugins.  We only need
    # to send some of the data from the sample objects, since a lot
    # of the fields are the same.
    instance = Instance(context, instance_ref)
    samples = gatherer(instance)
    payload['samples'] = [{'name': s.name,
                           'type': s.type,
                           'unit': s.unit,
                           'volume': s.volume}
                          for s in samples]

    publisher_id = notifier_api.publisher_id('compute', None)

    # We could simply modify the incoming message payload, but we
    # can't be sure that this notifier will be called before the RPC
    # notifier. Modifying the content may also break the message
    # signature. So, we start a new message publishing. We will be
    # called again recursively as a result, but we ignore the event we
    # generate so it doesn't matter.
    notifier_api.notify(context, publisher_id,
                        'compute.instance.delete.samples',
                        notifier_api.INFO, payload)
