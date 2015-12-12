# -*- coding: utf-8 -*-
# Copyright 2013-2015 eNovance <licensing@enovance.com>
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

from oslo_config import cfg
import oslo_context.context
import oslo_messaging
from oslo_messaging import serializer as oslo_serializer

DEFAULT_URL = "__default__"
TRANSPORTS = {}


def setup():
    oslo_messaging.set_transport_defaults('ceilometer')


def get_transport(url=None, optional=False, cache=True):
    """Initialise the oslo_messaging layer."""
    global TRANSPORTS, DEFAULT_URL
    cache_key = url or DEFAULT_URL
    transport = TRANSPORTS.get(cache_key)
    if not transport or not cache:
        try:
            transport = oslo_messaging.get_transport(cfg.CONF, url)
        except oslo_messaging.InvalidTransportURL as e:
            if not optional or e.url:
                # NOTE(sileht): oslo_messaging is configured but unloadable
                # so reraise the exception
                raise
            return None
        else:
            if cache:
                TRANSPORTS[cache_key] = transport
    return transport


def cleanup():
    """Cleanup the oslo_messaging layer."""
    global TRANSPORTS, NOTIFIERS
    NOTIFIERS = {}
    for url in TRANSPORTS:
        TRANSPORTS[url].cleanup()
        del TRANSPORTS[url]


class RequestContextSerializer(oslo_messaging.Serializer):

    def __init__(self, base):
        self._base = base

    def serialize_entity(self, context, entity):
        if not self._base:
            return entity
        return self._base.serialize_entity(context, entity)

    def deserialize_entity(self, context, entity):
        if not self._base:
            return entity
        return self._base.deserialize_entity(context, entity)

    def serialize_context(self, context):
        return context.to_dict()

    def deserialize_context(self, context):
        return oslo_context.context.RequestContext.from_dict(context)


_SERIALIZER = RequestContextSerializer(
    oslo_serializer.JsonPayloadSerializer())


def get_rpc_server(transport, topic, endpoint):
    """Return a configured oslo_messaging rpc server."""
    cfg.CONF.import_opt('host', 'ceilometer.service')
    target = oslo_messaging.Target(server=cfg.CONF.host, topic=topic)
    return oslo_messaging.get_rpc_server(transport, target,
                                         [endpoint], executor='threading',
                                         serializer=_SERIALIZER)


def get_rpc_client(transport, retry=None, **kwargs):
    """Return a configured oslo_messaging RPCClient."""
    target = oslo_messaging.Target(**kwargs)
    return oslo_messaging.RPCClient(transport, target,
                                    serializer=_SERIALIZER,
                                    retry=retry)


def get_notification_listener(transport, targets, endpoints,
                              allow_requeue=False):
    """Return a configured oslo_messaging notification listener."""
    return oslo_messaging.get_notification_listener(
        transport, targets, endpoints, executor='threading',
        allow_requeue=allow_requeue)


def get_notifier(transport, publisher_id):
    """Return a configured oslo_messaging notifier."""
    notifier = oslo_messaging.Notifier(transport, serializer=_SERIALIZER)
    return notifier.prepare(publisher_id=publisher_id)


def convert_to_old_notification_format(priority, ctxt, publisher_id,
                                       event_type, payload, metadata):
    # FIXME(sileht): temporary convert notification to old format
    # to focus on oslo_messaging migration before refactoring the code to
    # use the new oslo_messaging facilities
    notification = {'priority': priority,
                    'payload': payload,
                    'event_type': event_type,
                    'publisher_id': publisher_id}
    notification.update(metadata)
    for k in ctxt:
        notification['_context_' + k] = ctxt[k]
    return notification
