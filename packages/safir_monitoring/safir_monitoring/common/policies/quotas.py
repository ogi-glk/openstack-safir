# Copyright 2021 99cloud
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo_policy import policy

from safir_monitoring.common.policies import base

quota_policies = [
    policy.DocumentedRuleDefault(
        name='quota:get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get project quotas',
        operations=[{'path': '/quotas',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='quota:get_host',
        check_str=base.ROLE_ADMIN,
        description='Get host-level quotas',
        operations=[{'path': '/host_quotas',
                    'method': 'GET'}],
    ),
]


def list_rules():
    return quota_policies