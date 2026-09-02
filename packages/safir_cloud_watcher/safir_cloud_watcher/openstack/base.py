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

from openstack import connection
from oslo_config import cfg

from keystoneauth1 import loading as ks_loading


OPENSTACK_AUTH_OPTS = 'openstack_auth'
openstack_auth_opts = ks_loading.get_auth_common_conf_options()

cfg.CONF.register_opts(openstack_auth_opts, OPENSTACK_AUTH_OPTS)
ks_loading.register_session_conf_options(
    cfg.CONF,
    OPENSTACK_AUTH_OPTS)
ks_loading.register_auth_conf_options(
    cfg.CONF,
    OPENSTACK_AUTH_OPTS)


class BaseConnector(object):
    def __init__(self, **kwargs):
        self.auth = ks_loading.load_auth_from_conf_options(
            cfg.CONF,
            OPENSTACK_AUTH_OPTS)
        self.session = ks_loading.load_session_from_conf_options(
            cfg.CONF,
            OPENSTACK_AUTH_OPTS,
            auth=self.auth)
        self._openstack_conn = connection.Connection(session=self.session)
