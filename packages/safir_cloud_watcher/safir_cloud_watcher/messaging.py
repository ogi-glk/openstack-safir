# -*- coding: utf-8 -*-
# Copyright 2016 99Cloud zhangguoqing <zhang.guoqing@99cloud.net>
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
from oslo_messaging._drivers import impl_rabbit
from oslo_messaging.notify import notifier
from oslo_messaging import rpc
from oslo_messaging import serializer as oslo_serializer

DEFAULT_URL = "__default__"
RPC_TARGET = None
TRANSPORTS = {}


def setup():
    oslo_messaging.set_transport_defaults('safir_cloud_watcher')
    # NOTE(sileht): When batch is not enabled, oslo.messaging read all messages
    # in the queue and can consume a lot of memory, that works for rpc because
    # you never have a lot of message, but not good for notification. The
    # default is not changeable on oslo.messaging side. And we can't expose
    # this option to set set_transport_defaults because it a driver option.
    # 100 allow to prefetch a lot of messages but limit memory to 1G per
    # workers in worst case (~ 1M Nova notification)
    # And even driver options are located in private module, this is not going
    # to break soon.
    cfg.set_defaults(
        impl_rabbit.rabbit_opts,
        rabbit_qos_prefetch_count=100,
    )


def get_transport(conf, url=None, rpc=False, optional=False, cache=True):
    """Initialise the oslo_messaging layer."""
    global TRANSPORTS, DEFAULT_URL
    cache_key = url or DEFAULT_URL
    transport = TRANSPORTS.get(cache_key)
    if not transport or not cache:
        try:
            if rpc:
                transport = oslo_messaging.get_rpc_transport(conf, url)
            else:
                transport = notifier.get_notification_transport(conf, url)
        except (oslo_messaging.InvalidTransportURL,
                oslo_messaging.DriverLoadFailure):
            if not optional or url:
                # NOTE(sileht): oslo_messaging is configured but unloadable
                # so reraise the exception
                raise
            return None
        else:
            if cache:
                TRANSPORTS[cache_key] = transport
    return transport


def get_target():
    global RPC_TARGET
    if RPC_TARGET is None:
        RPC_TARGET = oslo_messaging.Target(topic='safir_cloud_watcher',
                                           version='1.0')
    return RPC_TARGET


def get_client(version_cap=None):
    transport = get_transport(cfg.CONF, rpc=True)
    target = get_target()
    return oslo_messaging.RPCClient(transport, target, version_cap=version_cap)


def get_server(target=None, endpoints=None):
    access_policy = rpc.dispatcher.DefaultRPCAccessPolicy
    transport = get_transport(cfg.CONF, rpc=True)
    if not target:
        target = get_target()
    return oslo_messaging.get_rpc_server(transport, target,
                                         endpoints, executor='eventlet',
                                         access_policy=access_policy)


def cleanup():
    """Cleanup the oslo_messaging layer."""
    global TRANSPORTS, NOTIFIERS
    NOTIFIERS = {}
    for url in TRANSPORTS:
        TRANSPORTS[url].cleanup()
        del TRANSPORTS[url]


_SERIALIZER = oslo_serializer.JsonPayloadSerializer()


def get_batch_notification_listener(transport, targets, endpoints,
                                    allow_requeue=False,
                                    batch_size=1, batch_timeout=None):
    """Return a configured oslo_messaging notification listener."""
    return oslo_messaging.get_batch_notification_listener(
        transport, targets, endpoints, executor='threading',
        allow_requeue=allow_requeue,
        batch_size=batch_size, batch_timeout=batch_timeout)


def get_notifier(transport, publisher_id):
    """Return a configured oslo_messaging notifier."""
    notifier = oslo_messaging.Notifier(transport, serializer=_SERIALIZER)
    return notifier.prepare(publisher_id=publisher_id)