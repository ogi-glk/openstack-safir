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

import safir_monitoring.db.base
import safir_monitoring.common.defaults
import safir_monitoring.main

__all__ = ['list_opts']

_opts = [
    ('database', list(itertools.chain(
        safir_monitoring.db.base.db_opts))),
    ('api_server', list(itertools.chain(
        safir_monitoring.main.api_server_opts))),
    ('opensearch', list(itertools.chain(
        safir_monitoring.main.opensearch_opts))),
    ('email_notifier', list(itertools.chain(
        safir_monitoring.main.email_notifier_opts))),
    (None, list(itertools.chain(
        safir_monitoring.main.common_opts))),
    ('thanos', list(itertools.chain(
    safir_monitoring.main.thanos_opts)))
]


def list_opts():
    return [(g, copy.deepcopy(o)) for g, o in _opts]