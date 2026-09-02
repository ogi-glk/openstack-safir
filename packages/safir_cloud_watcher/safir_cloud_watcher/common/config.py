# -*- coding: utf-8 -*-
# Copyright 2014 Objectif Libre
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
#
import copy
import itertools

import safir_cloud_watcher.api.app
import safir_cloud_watcher.cloud_operator.operation
import safir_cloud_watcher.openstack.base
import safir_cloud_watcher.service
import safir_cloud_watcher.licence.licence_watcher

__all__ = ['list_opts']

_opts = [
    ('api', list(itertools.chain(
        safir_cloud_watcher.api.app.api_opts,))),
    ('watcher', list(itertools.chain(
        safir_cloud_watcher.licence.licence_watcher.watcher_opts))),
    ('openstack_auth', list(itertools.chain(
        safir_cloud_watcher.openstack.base.openstack_auth_opts))),
    (None, list(itertools.chain(
        safir_cloud_watcher.api.app.auth_opts,
        safir_cloud_watcher.service.service_opts)))
]


def list_opts():
    return [(g, copy.deepcopy(o)) for g, o in _opts]
