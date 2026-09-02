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

metric_policies = [
    policy.DocumentedRuleDefault(
        name='metric:get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get metrics for a project (owner)',
        operations=[{'path': '/metrics',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_admin',
        check_str=base.ROLE_ADMIN,
        description='Get all metrics without project filter (admin only)',
        operations=[{'path': '/metrics',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_measurements',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get metric measurements (owner or admin)',
        operations=[{'path': '/metrics/measurements',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_statistics',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get metric statistics (owner or admin)',
        operations=[{'path': '/metrics/statistics',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_names',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='List metric names',
        operations=[{'path': '/metrics/names',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_dimensions',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get dimension names and values',
        operations=[{'path': '/metrics/dimensions/names',
                    'method': 'GET'},
                   {'path': '/metrics/dimensions/values',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_hosts',
        check_str=base.ROLE_ADMIN,
        description='List hosts (admin only)',
        operations=[{'path': '/metrics/hosts',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_vms',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='List VMs (owner or admin)',
        operations=[{'path': '/metrics/vms',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_top_n_host',
        check_str=base.ROLE_ADMIN,
        description='Get top N hosts by metric (admin only)',
        operations=[{'path': '/metrics/statistics/top-n-host',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_top_n_vm',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get top N VMs by metric (owner or admin)',
        operations=[{'path': '/metrics/statistics/top-n-vm',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_wow_change',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get week-over-week change (owner or admin)',
        operations=[{'path': '/metrics/forecasts/wow-change',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_prediction',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get resource prediction (owner or admin)',
        operations=[{'path': '/metrics/forecasts/prediction',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_prediction_system',
        check_str=base.ROLE_ADMIN,
        description='Get system-wide prediction (admin only)',
        operations=[{'path': '/metrics/forecasts/prediction/system',
                    'method': 'GET'},
                   {'path': '/metrics/forecasts/prediction/system/report',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_trend_graph',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get trend graph data (owner or admin)',
        operations=[{'path': '/metrics/forecasts/trend-graph',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_trend_graph_system',
        check_str=base.ROLE_ADMIN,
        description='Get system-wide trend graph (admin only)',
        operations=[{'path': '/metrics/forecasts/trend-graph/system',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_max_value',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get predicted max value (owner or admin)',
        operations=[{'path': '/metrics/forecasts/max-value',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_rightsizing',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get rightsizing reports (owner or admin)',
        operations=[{'path': '/metrics/rightsizing/idle-vms',
                    'method': 'GET'},
                   {'path': '/metrics/rightsizing/over-provisioned-vms',
                    'method': 'GET'},
                   {'path': '/metrics/rightsizing/under-provisioned-vms',
                    'method': 'GET'},
                   {'path': '/metrics/rightsizing/report',
                    'method': 'GET'}],
    ),
]


def list_rules():
    return metric_policies