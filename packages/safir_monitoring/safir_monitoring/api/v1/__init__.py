from fastapi import APIRouter

from safir_monitoring.api.v1 import alert_webhook
from safir_monitoring.api.v1 import notification
from safir_monitoring.api.v1 import alarm_rule
from safir_monitoring.api.v1 import quotas
from safir_monitoring.api.v1 import metric
from safir_monitoring.api.v1 import alarm_history
from safir_monitoring.api.v1 import metric_discovery
from safir_monitoring.api.v1 import metric_operations
from safir_monitoring.api.v1 import metric_forecasting
from safir_monitoring.api.v1 import metric_rightsizing
from safir_monitoring.api.v1 import report_schedule

api_router = APIRouter()

api_router.include_router(notification.router, tags=["notification"])
api_router.include_router(alarm_rule.router, tags=["alarm-rule"])
api_router.include_router(alert_webhook.router, tags=["alerts"])
api_router.include_router(quotas.router, tags=["quotas"])
api_router.include_router(metric.router, tags=["metric"])
api_router.include_router(alarm_history.router, tags=["alarm-history"])
api_router.include_router(metric_discovery.router, tags=["metric-discovery"])
api_router.include_router(metric_operations.router, tags=["metric-operations"])
api_router.include_router(metric_forecasting.router, tags=["metric-forecasting"])
api_router.include_router(metric_rightsizing.router, tags=["metric-rightsizing"])
api_router.include_router(report_schedule.router, tags=["reports"])