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

from oslo_policy import policy

from safir_cloud_watcher.policies import base

info_policies = [
    policy.DocumentedRuleDefault(
        name='handshake:list',
        check_str=base.ROLE_ADMIN,
        description='List all handshakes.',
        operations=[{'path': '/v1/handshake',
                     'method': 'LIST'}]),
    policy.DocumentedRuleDefault(
        name='handshake:show',
        check_str=base.ROLE_ADMIN,
        description='Get one handshake record.',
        operations=[{'path': '/v1/handshake/{safir_app}',
                     'method': 'GET'}]),
    policy.DocumentedRuleDefault(
        name='handshake:delete',
        check_str=base.ROLE_ADMIN,
        description='Delete a handshake record.',
        operations=[{'path': '/v1/handshake/{safir_app}',
                     'method': 'DELETE'}]),
    policy.DocumentedRuleDefault(
        name='handshake:update',
        check_str=base.ROLE_ADMIN,
        description='Update handshake.',
        operations=[{'path': '/v1/handshake',
                     'method': 'PUT'}])
]


def list_rules():
    return info_policies
