# -*- coding: utf-8 -*-
# Copyright 2017 TUBITAK B3LAB
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


# Test Licence Checker Function


import testscenarios
from oslo_config import cfg

from safir_cloud_watcher.licence.licence_checker import LicenceChecker
from safir_cloud_watcher.context import get_admin_context

CONF = cfg.CONF
CONF.import_opt('licence_key', 'safir_cloud_watcher.licence', 'licence')


class TestLicenceValidation(testscenarios.TestWithScenarios):

    scenarios = [
        ('Tracking None, Expected result False',
         dict(licence_valid=True,
              conf_licence="""gAAAAABlbxNbak4DQIsYg0m6jmyFpvcn
                              ORNy1D5QtzhfWxYYcWt2Ij9zPFvrJtFu
                              L8QaSwIatLS827NrO2c6-SU4cWCJL9aE
                              _4Nvn_DZ-zHmDMRZwzO7CjcGxsvw0KBa
                              boSbqiv-lXpOEMjAn4aHQOHhDzSMgwLa
                              8A==""")),

        ('Tracking Licence Not Valid Case',
         dict(licence_valid=False,
              conf_licence="")),

        ('Tracking Licence Valid Case',
         dict(licence_valid=False,
              conf_licence="""gAAAAAB3bxNbak4DQIsYg0m6jmyFpvcn
                              ORNy1D5QtzhfWxYYcWt2Ij9zPFvrJtFu
                              L8QaSwIatLS827NrO2c6-SU4cWCJL9aE
                              _4Nvn_DZ-zHmDMR2wzO7CjcGxsvw0KBa
                              boSbqiv-lXpOEMjAn4aHQOHhDzSMgwLa
                              8A=="""))
    ]

    def test_check_licence(self):

        # Given
        CONF.licence.licence_key = self.conf_licence
        ctx = get_admin_context()
        # Run
        licence_info = LicenceChecker(ctx).check_licence()

        # Then
        self.assertEqual(self.licence_valid, licence_info.licence_valid)
