# -*- coding: utf-8 -*-
# !/usr/bin/env python
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
eventlet.monkey_patch()

from oslo_concurrency import lockutils
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging
from oslo_utils import uuidutils
from stevedore import driver
from tooz import coordination

from safir_cloud_watcher.licence.licence_watcher import LicenceWatcher
from safir_cloud_watcher.openstack.nova import NovaConnector
from safir_cloud_watcher import context
from safir_cloud_watcher import messaging


LOG = logging.getLogger(__name__)

CONF = cfg.CONF

RUN_PERIOD = 43200  # Run once in 12 hours

orchestrator_opts = [
    cfg.StrOpt('coordination_url',
               secret=True,
               help='Coordination driver URL',
               default='file:///var/lib/safir_cloud_watcher/locks'),
]

CONF.register_opts(orchestrator_opts, group='orchestrator')


class CloudWatcherEndpoint(object):
    target = oslo_messaging.Target(namespace='watcher',
                                   version='1.0')

    def __init__(self, orchestrator):
        self._global_reload = False
        self._pending_reload = []
        self._module_state = {}
        self._orchestrator = orchestrator

    def get_reload_list(self):
        lock = lockutils.lock('module-reload')
        with lock:
            reload_list = self._pending_reload
            self._pending_reload = []
            return reload_list

    def reload_modules(self, ctxt):
        LOG.info('Received reload modules command.')
        lock = lockutils.lock('module-reload')
        with lock:
            self._global_reload = True

    def reload_module(self, ctxt, name):
        LOG.info('Received reload command for module %s.', name)
        lock = lockutils.lock('module-reload')
        with lock:
            if name not in self._pending_reload:
                self._pending_reload.append(name)


class Worker:
    def __init__(self):
        self.nova_connector = NovaConnector()

        ctx = context.get_admin_context()
        self.processor = LicenceWatcher(ctx)

        super(Worker, self).__init__()

    def run(self):
        try:
            used_resource_count = self.nova_connector.get_core_count()
        except Exception as e:
            LOG.warning(
                'Error while collecting data %(error)s',
                {'error': e})
            used_resource_count = None

        if used_resource_count:
            LOG.info('Processing data.')
            self.processor.process(used_resource_count, RUN_PERIOD)


class Orchestrator(object):
    def __init__(self):
        # RPC
        # bkz: https://docs.openstack.org/nova/latest/reference/rpc.html
        # self.server = None
        # self._watcher_endpoint = CloudWatcherEndpoint(self)
        # self._init_messaging()

        # DLM
        # openstack/tooz: The Tooz project aims at centralizing the most
        # common distributed primitives like group membership protocol,
        # lock service and leader election by providing a coordination
        # API helping developers to build distributed applications.
        self.coord = coordination.get_coordinator(
            CONF.orchestrator.coordination_url,
            uuidutils.generate_uuid().encode('ascii'))
        self.coord.start()

        self._wait_time = RUN_PERIOD

    def _lock(self, resource_id):
        lock_name = b"safir_cloud_watcher-" + str(resource_id).encode('ascii')
        return self.coord.get_lock(lock_name)

    def _init_messaging(self):
        target = oslo_messaging.Target(topic='safir_cloud_watcher',
                                       server=CONF.host,
                                       version='1.0')

        endpoints = [
            self._watcher_endpoint,
        ]

        self.server = messaging.get_server(target, endpoints)

        self.server.start()

    def process(self):
        while True:
            LOG.info('Safir Cloud Watcher starts licence checking process.')
            worker = Worker()
            worker.run()

            self.coord.heartbeat()
            eventlet.sleep(self._wait_time)

    def terminate(self):
        LOG.info('Terminating Orchestrator')
        self.coord.stop()
