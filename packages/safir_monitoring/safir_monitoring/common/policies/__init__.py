import itertools

from safir_monitoring.common.policies import base
from safir_monitoring.common.policies import notification
from safir_monitoring.common.policies import alarm_rule
from safir_monitoring.common.policies import quotas
from safir_monitoring.common.policies import metric
from safir_monitoring.common.policies import alarm_history

def list_rules():
    return itertools.chain(
        base.list_rules(),
        notification.list_rules(),
        alarm_rule.list_rules(),
        quotas.list_rules(),
        metric.list_rules(),
        alarm_history.list_rules()
    )