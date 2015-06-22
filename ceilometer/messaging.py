# -*- coding: utf-8 -*-
# Copyright 2013 eNovance <licensing@enovance.com>
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


def get_rpc_server(transport, topic, endpoint):
    """Return a configured oslo_messaging rpc server."""
    cfg.CONF.import_opt('host', 'ceilometer.service')
    target = oslo_messaging.Target(server=cfg.CONF.host, topic=topic)
    serializer = oslo_serializer.RequestContextSerializer(
        oslo_serializer.JsonPayloadSerializer())
    return oslo_messaging.get_rpc_server(transport, target,
                                         [endpoint], executor='eventlet',
                                         serializer=serializer)


def get_rpc_client(transport, retry=None, **kwargs):
    """Return a configured oslo_messaging RPCClient."""
    target = oslo_messaging.Target(**kwargs)
    serializer = oslo_serializer.RequestContextSerializer(
        oslo_serializer.JsonPayloadSerializer())
    return oslo_messaging.RPCClient(transport, target,
                                    serializer=serializer,
                                    retry=retry)


def get_notification_listener(transport, targets, endpoints,
                              allow_requeue=False):
    """Return a configured oslo_messaging notification listener."""
    return oslo_messaging.get_notification_listener(
        transport, targets, endpoints, executor='eventlet',
        allow_requeue=allow_requeue)


def get_notifier(transport, publisher_id):
    """Return a configured oslo_messaging notifier."""
    serializer = oslo_serializer.RequestContextSerializer(
        oslo_serializer.JsonPayloadSerializer())
    notifier = oslo_messaging.Notifier(transport, serializer=serializer)
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
