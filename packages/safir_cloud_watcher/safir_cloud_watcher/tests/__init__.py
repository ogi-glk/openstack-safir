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

import mock
from oslo_config import fixture as config_fixture
from oslotest import base
import testscenarios

from safir_cloud_watcher.openstack import base as collector


class FakeConnectorModule(collector.BaseConnector):

    def __init__(self):
        super(FakeConnectorModule, self).__init__([], period=3600)


class TestCase(testscenarios.TestWithScenarios, base.BaseTestCase):
    scenarios = [
    ]

    def setUp(self):
        super(TestCase, self).setUp()
        self._conf_fixture = self.useFixture(config_fixture.Config())
        self.conf = self._conf_fixture.conf
        auth = mock.patch(
            'keystoneauth1.loading.load_auth_from_conf_options',
            return_value=dict())
        auth.start()
        self.auth = auth
        session = mock.patch(
            'keystoneauth1.loading.load_session_from_conf_options',
            return_value=dict())
        session.start()
        self.session = session

    def tearDown(self):
        self.auth.stop()
        self.session.stop()
        super(TestCase, self).tearDown()
