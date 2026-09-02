# Copyright 2017 TUBITAK B3LAB
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

from safir_monitoring.common.policies import base

alarm_rule_policies = [
    policy.DocumentedRuleDefault(
        name='alarm_rule:list',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='List all alarm rules for a project',
        operations=[{'path': '/alarm-rules',
                     'method': 'GET'}]),
    policy.DocumentedRuleDefault(
        name='alarm_rule:get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get a specific alarm rule',
        operations=[{'path': '/alarm-rules/{alarm_rule_id}',
                     'method': 'GET'}]),
    policy.DocumentedRuleDefault(
        name='alarm_rule:create',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Create a new alarm rule for a project',
        operations=[{'path': '/alarm-rules',
                     'method': 'POST'}]),
    policy.DocumentedRuleDefault(
        name='alarm_rule:update',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Update an alarm rule',
        operations=[{'path': '/alarm-rules/{alarm_rule_id}',
                     'method': 'PUT'}]),
    policy.DocumentedRuleDefault(
        name='alarm_rule:delete',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Delete an alarm rule',
        operations=[{'path': '/alarm-rules/{alarm_rule_id}',
                     'method': 'DELETE'}]),
    policy.DocumentedRuleDefault(
        name='alarm_rule:toggle',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Enable or disable an alarm rule',
        operations=[{'path': '/alarm-rules/{alarm_rule_id}/toggle',
                     'method': 'POST'}]),
]


def list_rules():
    return alarm_rule_policies