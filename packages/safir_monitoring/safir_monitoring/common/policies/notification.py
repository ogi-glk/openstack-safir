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

notification_policies = [
    policy.DocumentedRuleDefault(
        name='notification:list',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='List all notifications for a project',
        operations=[{'path': '/notifications',
                     'method': 'GET'}]),
    policy.DocumentedRuleDefault(
        name='notification:get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get a specific notification',
        operations=[{'path': '/notifications/{notification_id}',
                     'method': 'GET'}]),
    policy.DocumentedRuleDefault(
        name='notification:create',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Create a new notification for a project',
        operations=[{'path': '/notifications',
                     'method': 'POST'}]),
    policy.DocumentedRuleDefault(
        name='notification:update',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Update a notification',
        operations=[{'path': '/notifications/{notification_id}',
                     'method': 'PUT'}]),
    policy.DocumentedRuleDefault(
        name='notification:delete',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Delete a notification',
        operations=[{'path': '/notifications/{notification_id}',
                     'method': 'DELETE'}]),
]


def list_rules():
    return notification_policies