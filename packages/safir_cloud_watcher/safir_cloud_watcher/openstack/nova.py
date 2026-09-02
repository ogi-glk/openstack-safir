# -*- coding: utf-8 -*-
# Copyright 2021 TUBITAK B3LAB
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

import json

from novaclient import client as nova_client
from oslo_config import cfg

from safir_cloud_watcher.openstack import base
import logging

LOG = logging.getLogger(__name__)

CONF = cfg.CONF
LONG_NUM = 9999


class NovaConnector(base.BaseConnector):
    def __init__(self, **kwargs):
        super(NovaConnector, self).__init__(**kwargs)

        self._conn = nova_client.Client(version='2', session=self.session)

    def get_hypervisor_count(self):
        """ Get total hypervisor count """
        hypervisors = self._conn.hypervisors.list()
        hypervisor_count = len(hypervisors)

        return hypervisor_count

    def get_core_count(self):
        sum_cpu = 0
        hypervisors = self._conn.hypervisors.list()
        for hv in hypervisors:
            try:
                if hv.status.lower() == "enabled":
                    cpu_info = json.loads(str(hv.cpu_info))
                    cpu = cpu_info['topology']
                    sum_cpu += cpu['cells'] * cpu['cores']
            except AttributeError:
                LOG.error("Unable to fetch CPU Topology. Request help from safir.iletisim@tubitak.gov.tr")
                sum_cpu += LONG_NUM
            except Exception:
                LOG.error("Unable to fetch CPU Topology. Request help from safir.iletisim@tubitak.gov.tr")
                sum_cpu += LONG_NUM
        LOG.info("Current CPU core count is %d.", sum_cpu)
        return sum_cpu

    def disable_one_host(self):
        hypervisors = self._conn.hypervisors.list()
        hv_with_least_vm = None
        vm_count = 9999
        for hv in hypervisors:
            node = self._conn.hypervisors.get(hv.id).__dict__
            if node and node["status"].lower() == "enabled":
                hv = dict()
                try:
                    hv["hostname"] = node["service"]["host"]
                    hv["service_id"] = node["service"]["id"]
                    if int(node["running_vms"]) < vm_count:
                        hv_with_least_vm = hv
                except KeyError:
                    LOG.error("Hypervisor info key error.")
                    pass

        if hv_with_least_vm is not None:
            self._conn.services.disable(hv_with_least_vm["hostname"], binary='nova-compute')
        elif len(hypervisors) > 0:
            node = self._conn.hypervisors.get(hypervisors[0].id).__dict__
            if node:
                try:
                    hostname = node["hypervisor_hostname"]
                    self._conn.services.disable(hostname, binary='nova-compute')
                except KeyError:
                    LOG.error("Hypervisor info key error!")
                except AttributeError:
                    pass
            else:
                LOG.error("Hypervisor not found!")

    def disable_all_hosts(self):
        hypervisors = self._conn.hypervisors.list()
        for hv in hypervisors:
            node = self._conn.hypervisors.get(hv.id).__dict__
            if node:
                try:
                    hostname = node["hypervisor_hostname"]
                    self._conn.services.disable(hostname, binary='nova-compute')
                except KeyError:
                    LOG.error("Hypervisor info key error!")
                except AttributeError:
                    pass
            else:
                LOG.error("Hypervisor not found!")
