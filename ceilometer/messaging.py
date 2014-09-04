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

from oslo.config import cfg
import oslo.messaging
from oslo.serialization import jsonutils

from ceilometer.openstack.common import context

DEFAULT_URL = "__default__"
TRANSPORTS = {}

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


def setup():
    oslo.messaging.set_transport_defaults('ceilometer')


def get_transport(url=None, optional=False, cache=True):
    """Initialise the oslo.messaging layer."""
    global TRANSPORTS, DEFAULT_URL
    cache_key = url or DEFAULT_URL
    transport = TRANSPORTS.get(cache_key)
    if not transport or not cache:
        try:
            transport = oslo.messaging.get_transport(cfg.CONF, url,
                                                     aliases=_ALIASES)
        except oslo.messaging.InvalidTransportURL as e:
            if not optional or e.url:
                # NOTE(sileht): oslo.messaging is configured but unloadable
                # so reraise the exception
                raise
            return None
        else:
            if cache:
                TRANSPORTS[cache_key] = transport
    return transport


def cleanup():
    """Cleanup the oslo.messaging layer."""
    global TRANSPORTS, NOTIFIERS
    NOTIFIERS = {}
    for url in TRANSPORTS:
        TRANSPORTS[url].cleanup()
        del TRANSPORTS[url]


def get_rpc_server(transport, topic, endpoint):
    """Return a configured oslo.messaging rpc server."""
    cfg.CONF.import_opt('host', 'ceilometer.service')
    target = oslo.messaging.Target(server=cfg.CONF.host, topic=topic)
    serializer = RequestContextSerializer(JsonPayloadSerializer())
    return oslo.messaging.get_rpc_server(transport, target,
                                         [endpoint], executor='eventlet',
                                         serializer=serializer)


def get_rpc_client(transport, **kwargs):
    """Return a configured oslo.messaging RPCClient."""
    target = oslo.messaging.Target(**kwargs)
    serializer = RequestContextSerializer(JsonPayloadSerializer())
    return oslo.messaging.RPCClient(transport, target,
                                    serializer=serializer)


def get_notification_listener(transport, targets, endpoints,
                              allow_requeue=False):
    """Return a configured oslo.messaging notification listener."""
    return oslo.messaging.get_notification_listener(
        transport, targets, endpoints, executor='eventlet',
        allow_requeue=allow_requeue)


def get_notifier(transport, publisher_id):
    """Return a configured oslo.messaging notifier."""
    serializer = RequestContextSerializer(JsonPayloadSerializer())
    notifier = oslo.messaging.Notifier(transport, serializer=serializer)
    return notifier.prepare(publisher_id=publisher_id)


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
