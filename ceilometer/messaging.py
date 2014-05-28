# -*- coding: utf-8 -*-
# Copyright 2013 eNovance <licensing@enovance.com>
#
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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

import eventlet
from oslo.config import cfg
import oslo.messaging

from ceilometer.openstack.common import context
from ceilometer.openstack.common import jsonutils


TRANSPORT = None
NOTIFIER = None

_ALIASES = {
    'ceilometer.openstack.common.rpc.impl_kombu': 'rabbit',
    'ceilometer.openstack.common.rpc.impl_qpid': 'qpid',
    'ceilometer.openstack.common.rpc.impl_zmq': 'zmq',
}


class RequestContextSerializer(oslo.messaging.Serializer):
    def __init__(self, base):
        self._base = base

    def serialize_entity(self, ctxt, entity):
        if not self._base:
            return entity
        return self._base.serialize_entity(ctxt, entity)

    def deserialize_entity(self, ctxt, entity):
        if not self._base:
            return entity
        return self._base.deserialize_entity(ctxt, entity)

    @staticmethod
    def serialize_context(ctxt):
        return ctxt.to_dict()

    @staticmethod
    def deserialize_context(ctxt):
        return context.RequestContext(ctxt)


class JsonPayloadSerializer(oslo.messaging.NoOpSerializer):
    @classmethod
    def serialize_entity(cls, context, entity):
        return jsonutils.to_primitive(entity, convert_instances=True)


def setup(url=None):
    """Initialise the oslo.messaging layer."""
    global TRANSPORT, NOTIFIER

    if url and url.startswith("fake://"):
        # NOTE(sileht): oslo.messaging fake driver uses time.sleep
        # for task switch, so we need to monkey_patch it
        eventlet.monkey_patch(time=True)

    if not TRANSPORT:
        oslo.messaging.set_transport_defaults('ceilometer')
        TRANSPORT = oslo.messaging.get_transport(cfg.CONF, url,
                                                 aliases=_ALIASES)
    if not NOTIFIER:
        serializer = RequestContextSerializer(JsonPayloadSerializer())
        NOTIFIER = oslo.messaging.Notifier(TRANSPORT, serializer=serializer)


def cleanup():
    """Cleanup the oslo.messaging layer."""
    global TRANSPORT, NOTIFIER
    assert TRANSPORT is not None
    assert NOTIFIER is not None
    TRANSPORT.cleanup()
    TRANSPORT = NOTIFIER = None


def get_rpc_server(topic, endpoint):
    """Return a configured oslo.messaging rpc server."""
    global TRANSPORT
    target = oslo.messaging.Target(server=cfg.CONF.host, topic=topic)
    serializer = RequestContextSerializer(JsonPayloadSerializer())
    return oslo.messaging.get_rpc_server(TRANSPORT, target, [endpoint],
                                         executor='eventlet',
                                         serializer=serializer)


def get_rpc_client(**kwargs):
    """Return a configured oslo.messaging RPCClient."""
    global TRANSPORT
    target = oslo.messaging.Target(**kwargs)
    serializer = RequestContextSerializer(JsonPayloadSerializer())
    return oslo.messaging.RPCClient(TRANSPORT, target,
                                    serializer=serializer)


def get_notification_listener(targets, endpoints, url=None):
    """Return a configured oslo.messaging notification listener."""
    global TRANSPORT
    if url:
        transport = oslo.messaging.get_transport(cfg.CONF, url,
                                                 _ALIASES)
    else:
        transport = TRANSPORT
    return oslo.messaging.get_notification_listener(
        transport, targets, endpoints, executor='eventlet')


def get_notifier(publisher_id):
    """Return a configured oslo.messaging notifier."""
    global NOTIFIER
    return NOTIFIER.prepare(publisher_id=publisher_id)


def convert_to_old_notification_format(priority, ctxt, publisher_id,
                                       event_type, payload, metadata):
    # FIXME(sileht): temporary convert notification to old format
    # to focus on oslo.messaging migration before refactoring the code to
    # use the new oslo.messaging facilities
    notification = {'priority': priority,
                    'payload': payload,
                    'event_type': event_type,
                    'publisher_id': publisher_id}
    notification.update(metadata)
    for k in ctxt:
        notification['_context_' + k] = ctxt[k]
    return notification
