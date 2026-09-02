from oslo_policy import policy
from safir_monitoring.common.policies import base

alarm_history_policies = [
    policy.DocumentedRuleDefault(
        name='alarm_history:list',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='List alarm history for a project',
        operations=[{'path': '/alarm-history',
                     'method': 'GET'}]),
]


def list_rules():
    return alarm_history_policies